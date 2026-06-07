#!/usr/bin/env python3
"""Offline sentinel for release cloud upload guardrails.

This checker is deliberately static. It must never read credentials, invoke
provider CLIs, or call cloud APIs. Its job is to catch CI, pre-commit, and
release validation scripts that accidentally opt into live cloud release
uploads instead of staying on dry-run, mock, or fake-gcloud paths.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


LIVE_CLOUD_UPLOAD_ENV = "CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD"
DRY_RUN_BUCKET = "crossgl-release-dry-run"
SCAN_FILE_NAMES = {
    ".pre-commit-config.yaml",
    "tools/check_package_recover_fixtures.py",
}
SCAN_TOOL_NAME_RE = re.compile(r"(release|publish|cloud|guardrail)", re.IGNORECASE)
SCAN_EXTENSIONS = {".py", ".sh", ".ps1", ".cmake"}
WORKFLOW_EXTENSIONS = {".yml", ".yaml"}
TRUTHY_OPT_IN_RE = re.compile(
    rf"\b{re.escape(LIVE_CLOUD_UPLOAD_ENV)}\b\s*[:=]\s*['\"]?"
    r"(1|true|yes|on)['\"]?\b",
    re.IGNORECASE,
)
CONFIG_LIVE_CLOUD_OPT_IN_BINDING_RE = re.compile(
    rf"\b{re.escape(LIVE_CLOUD_UPLOAD_ENV)}\b['\"]?\s*[:=]",
    re.IGNORECASE,
)
CONFIG_GCP_CREDENTIAL_BINDING_RE = re.compile(
    r"\bGOOGLE_APPLICATION_CREDENTIALS\b(?:['\"]?\])?['\"]?\s*[:=]",
    re.IGNORECASE,
)
REAL_CREDENTIAL_PATH_RE = re.compile(
    r"\bGOOGLE_APPLICATION_CREDENTIALS\b(?:['\"]?\])?\s*[:=]\s*['\"]?"
    r"((/[^\s'\"]+)|([A-Za-z]:\\[^\s'\"]+)|(\$\{\{\s*secrets\.))",
    re.IGNORECASE,
)
GCLOUD_COMMAND_RE = re.compile(r"\b(gcloud|gsutil)\b", re.IGNORECASE)
CLOUD_AUTH_RE = re.compile(
    r"\b(gcloud\s+auth|application-default|metadata service credentials)\b",
    re.IGNORECASE,
)
NETWORK_COMMAND_RE = re.compile(
    r"\b(curl|wget|Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer)\b"
    r"|\bpython(?:3(?:\.\d+)?)?\s+-m\s+(?:requests|urllib)\b",
    re.IGNORECASE,
)
GITHUB_COST_OR_ORG_QUERY_RE = re.compile(
    r"\bgh\s+api\b[^\n]*(?:\bbilling\b|\bactions/billing\b|"
    r"\bactions/permissions\b|\bsettings\b)"
    r"|\bapi\.github\.com/[^\s'\"]*(?:billing|actions/billing|"
    r"actions/permissions|settings)\b",
    re.IGNORECASE,
)
PUBLISH_COMMAND_RE = re.compile(
    r"\bgh\s+release\s+(?:create|upload|edit|delete)\b"
    r"|\b(?:python(?:3(?:\.\d+)?)?\s+-m\s+)?twine\s+upload\b"
    r"|\b(?:npm|pnpm)\s+publish\b"
    r"|\byarn\s+npm\s+publish\b"
    r"|\bcargo\s+publish\b"
    r"|\b(?:poetry|hatch)\s+publish\b"
    r"|\b(?:dotnet\s+)?nuget\s+push\b"
    r"|\bpython(?:3(?:\.\d+)?)?\s+setup\.py\s+upload\b"
    r"|\b(?:pypa/gh-action-pypi-publish|softprops/action-gh-release|"
    r"actions/create-release|google-github-actions/(?:auth|setup-gcloud|"
    r"upload-cloud-storage))@",
    re.IGNORECASE,
)
PYTHON_CLOUD_NETWORK_IMPORT_RE = re.compile(
    r"^\s*(?:"
    r"import\s+(?:requests|urllib\.request|http\.client|httplib2|google\.cloud|"
    r"google\.auth|googleapiclient)\b"
    r"|from\s+(?:requests|urllib\.request|http\.client|httplib2|google\.cloud|"
    r"google\.auth|googleapiclient)\b"
    r")",
    re.IGNORECASE,
)
GCP_NETWORK_ENDPOINT_RE = re.compile(
    r"\b(?:https?://)?(?:storage|www|oauth2|iamcredentials|sts)\.googleapis\.com\b"
    r"|\bmetadata\.google\.internal\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    message: str


def posix_path(path: Path) -> str:
    return path.as_posix()


def is_workflow_path(path: Path) -> bool:
    parts = path.parts
    return (
        len(parts) >= 3
        and parts[0] == ".github"
        and parts[1] == "workflows"
        and path.suffix in WORKFLOW_EXTENSIONS
    )


def is_config_path(path: Path) -> bool:
    return path.as_posix() == ".pre-commit-config.yaml" or is_workflow_path(path)


def is_release_script_path(path: Path) -> bool:
    path_text = path.as_posix()
    if path_text in SCAN_FILE_NAMES:
        return True
    if len(path.parts) >= 2 and path.parts[0] == "tools":
        return path.suffix in SCAN_EXTENSIONS and bool(
            SCAN_TOOL_NAME_RE.search(path.name)
        )
    if len(path.parts) >= 1 and path.parts[0] == "scripts":
        return path.suffix in SCAN_EXTENSIONS and bool(
            SCAN_TOOL_NAME_RE.search(path_text)
        )
    return False


def scan_paths(root: Path) -> list[Path]:
    candidates: list[Path] = []
    pre_commit = root / ".pre-commit-config.yaml"
    if pre_commit.exists():
        candidates.append(pre_commit)

    workflows = root / ".github" / "workflows"
    if workflows.exists():
        candidates.extend(
            path
            for path in workflows.rglob("*")
            if path.is_file() and path.suffix in WORKFLOW_EXTENSIONS
        )

    for directory_name in ("tools", "scripts"):
        directory = root / directory_name
        if not directory.exists():
            continue
        candidates.extend(
            path
            for path in directory.rglob("*")
            if path.is_file()
            and path.suffix in (SCAN_EXTENSIONS | WORKFLOW_EXTENSIONS)
            and is_release_script_path(path.relative_to(root))
        )

    ignored = {
        "tools/check_release_artifact_policy.py",
        "tools/check_release_cloud_guardrails.py",
    }
    return sorted(
        {
            path
            for path in candidates
            if path.relative_to(root).as_posix() not in ignored
        },
        key=lambda path: path.relative_to(root).as_posix(),
    )


def context(lines: list[str], index: int, radius: int = 40) -> str:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return "\n".join(lines[start:end]).lower()


def is_parser_or_error_context(ctx: str) -> bool:
    return any(
        token in ctx
        for token in (
            "add_argument",
            "help=",
            "expected",
            "without --allow-cloud-upload",
            "refusing live cloud",
            "must not",
            "does not accept",
            "requires --gcs-upload",
            "self-test",
            "parser.",
            "requires ",
            "must be false unless",
            "live cloud modes require",
            "requests live cloud mode",
            "live cloud upload mode",
        )
    )


def is_fake_or_dry_run_context(ctx: str, line: str) -> bool:
    lowered = line.lower()
    return any(
        token in ctx or token in lowered
        for token in (
            "fake_gcloud",
            "fake-gcloud",
            "fake gcloud",
            "crossgl_fake_gcloud",
            "mock-upload",
            "mock_upload",
            "dry-run",
            "dry_run",
            "local-only",
            "local_only",
            "preflight",
            "missing_credentials",
            "missing-credentials",
            DRY_RUN_BUCKET,
        )
    )


def is_credential_shape_context(ctx: str, line: str) -> bool:
    lowered = line.lower()
    return any(
        token in ctx or token in lowered
        for token in (
            "credentialenv",
            "credentialsenv",
            "expected_credentials_env",
            "missing_credentials",
            "fake_credentials",
            "fake_gcloud",
            "fake-gcloud",
            "fake google application credentials",
        )
    )


def add_finding(
    findings: list[Finding],
    path: Path,
    line_number: int,
    code: str,
    message: str,
) -> None:
    findings.append(
        Finding(
            path=posix_path(path),
            line=line_number,
            code=code,
            message=message,
        )
    )


def check_config_line(
    findings: list[Finding],
    path: Path,
    line_number: int,
    line: str,
) -> None:
    if CONFIG_LIVE_CLOUD_OPT_IN_BINDING_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "live-cloud-opt-in",
            f"{LIVE_CLOUD_UPLOAD_ENV} must not be bound in CI/pre-commit",
        )
    if "--allow-cloud-upload" in line:
        add_finding(
            findings,
            path,
            line_number,
            "live-cloud-flag",
            "--allow-cloud-upload must not be used by CI/pre-commit defaults",
        )
    if "--gcs-upload" in line:
        add_finding(
            findings,
            path,
            line_number,
            "live-gcs-upload",
            "--gcs-upload must not be used by CI/pre-commit defaults",
        )
    if CONFIG_GCP_CREDENTIAL_BINDING_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "real-credential-reference",
            "CI/pre-commit must not bind GOOGLE_APPLICATION_CREDENTIALS",
        )
    if "gs://" in line and DRY_RUN_BUCKET not in line:
        add_finding(
            findings,
            path,
            line_number,
            "real-cloud-destination",
            "CI/pre-commit must not reference live gs:// destinations",
        )
    if GCLOUD_COMMAND_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "real-cloud-cli",
            "CI/pre-commit must not invoke gcloud or gsutil",
        )
    if NETWORK_COMMAND_RE.search(line) or GCP_NETWORK_ENDPOINT_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "network-api",
            "CI/pre-commit must not add release cloud HTTP/API access",
        )
    if GITHUB_COST_OR_ORG_QUERY_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "live-cost-query",
            "CI/pre-commit must not query live billing or organization settings",
        )
    if PUBLISH_COMMAND_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "publish-command",
            "CI/pre-commit must not invoke live package or release publishing",
        )


def check_release_script_line(
    findings: list[Finding],
    path: Path,
    lines: list[str],
    index: int,
) -> None:
    line = lines[index]
    line_number = index + 1
    ctx = context(lines, index)

    if TRUTHY_OPT_IN_RE.search(line) and "self-test" not in ctx:
        add_finding(
            findings,
            path,
            line_number,
            "live-cloud-opt-in",
            f"{LIVE_CLOUD_UPLOAD_ENV} truthy default is only allowed in self-tests",
        )

    if "--allow-cloud-upload" in line and not is_parser_or_error_context(ctx):
        add_finding(
            findings,
            path,
            line_number,
            "live-cloud-flag",
            "release scripts must not pass --allow-cloud-upload by default",
        )

    if "--gcs-upload" in line and not (
        is_parser_or_error_context(ctx) or is_fake_or_dry_run_context(ctx, line)
    ):
        add_finding(
            findings,
            path,
            line_number,
            "live-gcs-upload",
            "--gcs-upload is only allowed in fake-gcloud, mock, or dry-run tests",
        )

    if REAL_CREDENTIAL_PATH_RE.search(line):
        add_finding(
            findings,
            path,
            line_number,
            "real-credential-reference",
            "release scripts must not bind GOOGLE_APPLICATION_CREDENTIALS paths",
        )
    elif "GOOGLE_APPLICATION_CREDENTIALS" in line and not (
        is_credential_shape_context(ctx, line) or is_fake_or_dry_run_context(ctx, line)
    ):
        add_finding(
            findings,
            path,
            line_number,
            "credential-reference",
            "credential references must stay in manifest fields or fake shims",
        )

    if (
        "gs://" in line
        and DRY_RUN_BUCKET not in line
        and "cloud_uri_prefixes" not in line.lower()
        and not is_parser_or_error_context(ctx)
        and not is_fake_or_dry_run_context(ctx, line)
    ):
        add_finding(
            findings,
            path,
            line_number,
            "real-cloud-destination",
            "release scripts must not embed live gs:// destinations",
        )

    commandish = any(token in line for token in ("subprocess", "[", "run:", "entry:"))
    if (
        GCLOUD_COMMAND_RE.search(line)
        and commandish
        and not is_fake_or_dry_run_context(ctx, line)
        and not is_parser_or_error_context(ctx)
    ):
        add_finding(
            findings,
            path,
            line_number,
            "real-cloud-cli",
            "gcloud/gsutil invocation must be isolated to fake-gcloud shims",
        )

    if CLOUD_AUTH_RE.search(line) and not is_parser_or_error_context(ctx):
        add_finding(
            findings,
            path,
            line_number,
            "ambient-cloud-auth",
            "release scripts must not rely on ambient cloud authentication",
        )

    if (
        (
            NETWORK_COMMAND_RE.search(line)
            or PYTHON_CLOUD_NETWORK_IMPORT_RE.search(line)
            or GCP_NETWORK_ENDPOINT_RE.search(line)
        )
        and not is_fake_or_dry_run_context(ctx, line)
        and not is_parser_or_error_context(ctx)
    ):
        add_finding(
            findings,
            path,
            line_number,
            "network-api",
            "release scripts must not add cloud HTTP clients, SDK imports, or API endpoints",
        )

    if GITHUB_COST_OR_ORG_QUERY_RE.search(line) and not is_parser_or_error_context(ctx):
        add_finding(
            findings,
            path,
            line_number,
            "live-cost-query",
            (
                "release scripts must keep cost reporting local/static/report-only "
                "and must not query live billing or organization settings"
            ),
        )

    if PUBLISH_COMMAND_RE.search(line) and not is_parser_or_error_context(ctx):
        add_finding(
            findings,
            path,
            line_number,
            "publish-command",
            (
                "release scripts must not invoke live package or release publishing "
                "commands from readiness paths"
            ),
        )


def check_file(root: Path, path: Path) -> list[Finding]:
    relative = path.relative_to(root)
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: list[Finding] = []
    if is_config_path(relative):
        for index, line in enumerate(lines):
            check_config_line(findings, relative, index + 1, line)
        return findings

    for index in range(len(lines)):
        check_release_script_line(findings, relative, lines, index)
    return findings


def check_repository(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in scan_paths(root):
        findings.extend(check_file(root, path))
    return findings


def check_virtual_files(files: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    for name, text in sorted(files.items()):
        path = Path(name)
        lines = text.splitlines()
        if is_config_path(path):
            for index, line in enumerate(lines):
                check_config_line(findings, path, index + 1, line)
        else:
            for index in range(len(lines)):
                check_release_script_line(findings, path, lines, index)
    return findings


def run_self_test() -> list[str]:
    errors: list[str] = []
    allowed = {
        ".github/workflows/ci.yml": "steps:\n  - run: pre-commit run --all-files\n",
        ".pre-commit-config.yaml": (
            "repos:\n"
            "  - repo: local\n"
            "    hooks:\n"
            "      - id: release-cloud-guardrails\n"
            "        entry: python tools/check_release_cloud_guardrails.py --root .\n"
        ),
        "tools/check_package_release_publish_flow.py": (
            "def make_fake_gcloud_env(work_dir):\n"
            "    env = {}\n"
            "    env['GOOGLE_APPLICATION_CREDENTIALS'] = str(fake_credentials)\n"
            "    return env\n"
            "fake_env = make_fake_gcloud_env(work_dir)\n"
            "run_checked('fake-gcloud-upload', ['cglc', '--gcs-upload'], "
            "env=fake_env)\n"
        ),
        "tools/check_release_provenance_manifest.py": (
            "parser.add_argument('--allow-cloud-upload', action='store_true')\n"
            "raise CheckError('refusing live cloud without --allow-cloud-upload')\n"
        ),
    }
    allowed_findings = check_virtual_files(allowed)
    if allowed_findings:
        errors.append(
            "self-test: allowed dry-run/fake/parser examples produced findings: "
            + "; ".join(finding.code for finding in allowed_findings)
        )

    denied_cases: dict[str, tuple[dict[str, str], str]] = {
        "workflow opt-in": (
            {
                ".github/workflows/release.yml": (
                    "env:\n"
                    f"  {LIVE_CLOUD_UPLOAD_ENV}: 1\n"
                    "steps:\n"
                    "  - run: echo release\n"
                )
            },
            "live-cloud-opt-in",
        ),
        "workflow opt-in binding": (
            {
                ".github/workflows/release.yml": (
                    "env:\n"
                    f"  '{LIVE_CLOUD_UPLOAD_ENV}': "
                    "${{ secrets.CROSSGL_ALLOW_LIVE_CLOUD_RELEASE_UPLOAD }}\n"
                    "steps:\n"
                    "  - run: echo release\n"
                )
            },
            "live-cloud-opt-in",
        ),
        "pre-commit flag": (
            {
                ".pre-commit-config.yaml": (
                    "repos:\n"
                    "  - repo: local\n"
                    "    hooks:\n"
                    "      - id: bad\n"
                    "        entry: python tool.py --allow-cloud-upload\n"
                )
            },
            "live-cloud-flag",
        ),
        "pre-commit credential binding": (
            {
                ".pre-commit-config.yaml": (
                    "repos:\n"
                    "  - repo: local\n"
                    "    hooks:\n"
                    "      - id: bad\n"
                    "        entry: python tools/check_release_upload.py\n"
                    "        env:\n"
                    "          'GOOGLE_APPLICATION_CREDENTIALS': "
                    "${{ secrets.GCP_RELEASE_KEY }}\n"
                )
            },
            "real-credential-reference",
        ),
        "release gcloud": (
            {
                "tools/check_release_upload.py": (
                    "subprocess.run(['gcloud', 'storage', 'cp', src, dst])\n"
                )
            },
            "real-cloud-cli",
        ),
        "release gcs upload": (
            {
                "tools/check_release_upload.py": (
                    "run_checked('upload', ['cglc', 'package', 'release', "
                    "'--gcs-upload'])\n"
                )
            },
            "live-gcs-upload",
        ),
        "real credential": (
            {
                "tools/check_release_upload.py": (
                    "env['GOOGLE_APPLICATION_CREDENTIALS'] = '/tmp/key.json'\n"
                )
            },
            "real-credential-reference",
        ),
        "workflow network api": (
            {
                ".github/workflows/release.yml": (
                    "steps:\n"
                    "  - run: curl https://storage.googleapis.com/release-bucket\n"
                )
            },
            "network-api",
        ),
        "release sdk import": (
            {
                "tools/check_release_upload.py": (
                    "from google.cloud import storage\nclient = storage.Client()\n"
                )
            },
            "network-api",
        ),
        "release google endpoint": (
            {
                "tools/check_release_upload.py": (
                    "endpoint = 'https://storage.googleapis.com/upload/storage/v1/b'\n"
                )
            },
            "network-api",
        ),
        "workflow publish action": (
            {
                ".github/workflows/release.yml": (
                    "steps:\n  - uses: pypa/gh-action-pypi-publish@v1\n"
                )
            },
            "publish-command",
        ),
        "release publish command": (
            {
                "tools/check_release_upload.py": (
                    "subprocess.run('gh release create v0.1.0', shell=True)\n"
                )
            },
            "publish-command",
        ),
        "workflow live cost query": (
            {
                ".github/workflows/release.yml": (
                    "steps:\n  - run: gh api /orgs/crossgl/settings/billing\n"
                )
            },
            "live-cost-query",
        ),
    }
    for label, (files, expected_code) in denied_cases.items():
        findings = check_virtual_files(files)
        if not any(finding.code == expected_code for finding in findings):
            errors.append(
                f"self-test: {label} did not produce {expected_code}; "
                f"got {[finding.code for finding in findings]!r}"
            )
    return errors


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="CrossGL-Compiler repository root",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run offline checker self-tests instead of validating a repository",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        errors = run_self_test()
    else:
        errors = [
            f"{finding.path}:{finding.line}: {finding.code}: {finding.message}"
            for finding in check_repository(args.root.resolve())
        ]

    if errors:
        print("release cloud guardrails check failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if args.self_test:
        print("validated release cloud guardrails checker self-test")
    else:
        print("validated offline release cloud guardrails")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
