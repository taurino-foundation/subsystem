"""Check Taurino wheels without invoking their native extension.

Standard-library only; suitable for CI on all platforms.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys
import zipfile

EXPECTED = {
    "linux-gnu-x64": ("linux", "x86_64"),
    "linux-gnu-arm64": ("linux", "aarch64"),
    "windows-x64": ("win", "amd64"),
    "windows-arm64": ("win", "arm64"),
    "macos-intel": ("macosx", "x86_64"),
    "macos-arm64": ("macosx", "arm64"),
    "linux-musl-x64": ("musllinux", "x86_64"),
    "linux-musl-arm64": ("musllinux", "aarch64"),
}


def platform_of(target: str, kind: str) -> tuple[str, str]:
    if kind == "windows":
        return "win", "arm64" if target.startswith("aarch64") else "amd64"
    if kind == "macos":
        return "macosx", "arm64" if target.startswith("aarch64") else "x86_64"
    if kind == "musl":
        return "musllinux", "aarch64" if target.startswith("aarch64") else "x86_64"
    return "linux", "aarch64" if target.startswith("aarch64") else "x86_64"


def inspect_wheel(wheel: pathlib.Path) -> tuple[str, str, str]:
    parts = wheel.stem.split("-")
    if len(parts) < 5:
        raise ValueError(f"Invalid wheel filename: {wheel.name}")
    python_tag, abi_tag, platform_tag = parts[-3:]
    if not (python_tag == "cp39" and abi_tag == "abi3"):
        raise ValueError(f"Expected cp39-abi3 wheel, found {wheel.name}")
    with zipfile.ZipFile(wheel) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Corrupt wheel member: {bad}")
        if not any(n.endswith(".dist-info/WHEEL") for n in archive.namelist()):
            raise ValueError(f"Wheel metadata missing: {wheel.name}")
        if not any(n.endswith(".dist-info/RECORD") for n in archive.namelist()):
            raise ValueError(f"Wheel RECORD missing: {wheel.name}")
    return python_tag, abi_tag, platform_tag


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=pathlib.Path, required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--target", default="")
    parser.add_argument("--kind", default="")
    parser.add_argument("--all-targets", action="store_true")
    parser.add_argument("--copy-to", type=pathlib.Path)
    parser.add_argument("--checksum-file", type=pathlib.Path)
    args = parser.parse_args()
    wheels = sorted(args.directory.rglob("*.whl"))
    if len(wheels) != args.count:
        raise ValueError(f"Expected {args.count} wheel(s), got {len(wheels)}: {wheels}")
    seen_names: set[str] = set()
    seen_platforms: set[tuple[str, str]] = set()
    if args.copy_to:
        args.copy_to.mkdir(parents=True, exist_ok=True)
    digest_lines = []
    for wheel in wheels:
        if wheel.name in seen_names:
            raise ValueError(f"Duplicate wheel filename: {wheel.name}")
        seen_names.add(wheel.name)
        _, _, tag = inspect_wheel(wheel)
        matched = []
        for label, (platform, arch) in EXPECTED.items():
            # Accept macOS universal2 only for a single-architecture check;
            # the all-targets job needs distinct filenames.
            if (tag.startswith(platform + "_") or (platform == "macosx" and tag.startswith("macosx_"))) and (
                arch in tag or (platform == "macosx" and "universal2" in tag)
            ):
                matched.append(label)
        if args.all_targets:
            if len(matched) != 1:
                raise ValueError(f"Cannot uniquely classify {wheel.name}: {matched}")
            key = EXPECTED[matched[0]]
            if key in seen_platforms:
                raise ValueError(f"Duplicate platform {key}: {wheel.name}")
            seen_platforms.add(key)
        else:
            platform, arch = platform_of(args.target, args.kind)
            if platform not in tag or arch not in tag:
                raise ValueError(f"Unexpected wheel platform for {args.target}: {wheel.name}")
        sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
        digest_lines.append(f"{sha}  {wheel.name}")
        if args.copy_to:
            shutil.copy2(wheel, args.copy_to / wheel.name)
        print(f"VALID {wheel.name} SHA256={sha}")
    if args.all_targets and seen_platforms != set(EXPECTED.values()):
        raise ValueError(f"Missing platforms: {set(EXPECTED.values()) - seen_platforms}")
    if args.checksum_file:
        args.checksum_file.write_text("\n".join(digest_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
