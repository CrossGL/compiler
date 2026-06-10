#!/usr/bin/env python3
"""Create a deterministic ZIP_STORED archive from a package directory."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo


def package_members(package_dir: Path) -> list[Path]:
    return sorted(path for path in package_dir.rglob("*") if path.is_file())


def write_stored_member(archive: ZipFile, archive_name: str, payload: bytes) -> None:
    info = ZipInfo(archive_name)
    info.compress_type = ZIP_STORED
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.external_attr = 0o644 << 16
    archive.writestr(info, payload)


def write_stored_zip(
    package_dir: Path,
    output_path: Path,
    *,
    prefix: str | None,
    root_files: tuple[str, ...],
) -> None:
    package_dir = package_dir.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    top_level = package_dir.name if prefix is None else prefix

    with ZipFile(output_path, "w", compression=ZIP_STORED) as archive:
        for member in package_members(package_dir):
            relative_name = member.relative_to(package_dir)
            archive_name = (
                relative_name.as_posix()
                if top_level == ""
                else Path(top_level, relative_name).as_posix()
            )
            write_stored_member(archive, archive_name, member.read_bytes())
        for root_file in root_files:
            name, separator, text = root_file.partition("=")
            if (
                not separator
                or not name
                or name.startswith("/")
                or ".." in name.split("/")
            ):
                raise ValueError(f"invalid root file specification: {root_file!r}")
            write_stored_member(archive, name, text.encode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prefix")
    parser.add_argument("--no-prefix", action="store_true")
    parser.add_argument("--root-file", action="append", default=[])
    args = parser.parse_args()

    if not args.package_dir.is_dir():
        parser.error(f"package directory does not exist: {args.package_dir}")
    if args.no_prefix and args.prefix is not None:
        parser.error("--prefix and --no-prefix are mutually exclusive")
    prefix = "" if args.no_prefix else args.prefix
    write_stored_zip(
        args.package_dir,
        args.output,
        prefix=prefix,
        root_files=tuple(args.root_file),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
