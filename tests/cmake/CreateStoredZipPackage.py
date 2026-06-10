#!/usr/bin/env python3
"""Create a deterministic ZIP_STORED archive from a package directory."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


def package_members(package_dir: Path) -> list[Path]:
    return sorted(path for path in package_dir.rglob("*") if path.is_file())


def write_stored_zip(package_dir: Path, output_path: Path) -> None:
    package_dir = package_dir.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    top_level = package_dir.name

    with ZipFile(output_path, "w", compression=ZIP_STORED) as archive:
        for member in package_members(package_dir):
            archive_name = Path(top_level, member.relative_to(package_dir)).as_posix()
            info = ZipInfo(archive_name)
            info.compress_type = ZIP_STORED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o644 << 16
            archive.writestr(info, member.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    if not args.package_dir.is_dir():
        parser.error(f"package directory does not exist: {args.package_dir}")
    write_stored_zip(args.package_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
