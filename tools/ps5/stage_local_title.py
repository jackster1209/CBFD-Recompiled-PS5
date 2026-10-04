#!/usr/bin/env python3
"""Stage a private PS5 title folder with the user's validated ROM.

This is the packaging step for a future local ROM-to-PS5 builder. The input
title must already contain the user's locally compiled eboot.bin; this script
does not compile game code or create a public release archive.
"""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "out" / "ps5"
ROM_SHA1 = "4cbadd3c4e0729dec46af64ad018050eada4f47a"
ROM_NAME = "baserom.us.z64"
TITLE_ID = re.compile(r"PPSA[0-9]{5}\Z")


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_private_path(path: Path) -> None:
    if not OUTPUT_ROOT.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("the private PS5 output folder escaped the repository")
    if not path.resolve().is_relative_to(OUTPUT_ROOT.resolve()):
        raise ValueError("staging path escaped the private PS5 output folder")


def stage_title(title_dir: Path, rom: Path) -> Path:
    title_dir = title_dir.resolve(strict=True)
    rom = rom.resolve(strict=True)
    if not title_dir.is_dir() or not rom.is_file():
        raise ValueError("the title input must be a folder and the ROM must be a file")
    if rom.suffix.lower() != ".z64":
        raise ValueError("the ROM input must be a big-endian .z64 file")

    metadata = json.loads((title_dir / "sce_sys" / "param.json").read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("sce_sys/param.json must contain an object")
    title_id = metadata.get("titleId")
    if not isinstance(title_id, str) or not TITLE_ID.fullmatch(title_id):
        raise ValueError("sce_sys/param.json needs a PPSA##### titleId")
    if title_dir.name != title_id:
        raise ValueError("the title folder name must match param.json titleId")
    for required in ("eboot.bin", "sce_module/libc.prx"):
        if not (title_dir / required).is_file():
            raise ValueError(f"the locally built title is missing {required}")
    for path in title_dir.rglob("*"):
        if path.is_symlink():
            raise ValueError("the title folder must not contain symlinks")
    source_rom_dir = title_dir / "ROM"
    if source_rom_dir.exists() and any(source_rom_dir.iterdir()):
        raise ValueError("the input title's ROM folder must be empty")
    if sha1_file(rom) != ROM_SHA1:
        raise ValueError("the ROM is not the supported US big-endian .z64 image")

    require_private_path(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_ROOT / title_id
    require_private_path(destination)
    if destination.exists():
        raise ValueError(f"{destination} already exists; remove or archive it before staging another build")

    temporary = Path(tempfile.mkdtemp(prefix=".stage-", dir=OUTPUT_ROOT))
    require_private_path(temporary)
    try:
        shutil.copytree(title_dir, temporary, dirs_exist_ok=True)
        staged_rom = temporary / "ROM" / ROM_NAME
        staged_rom.parent.mkdir(exist_ok=True)
        shutil.copy2(rom, staged_rom)
        if sha1_file(staged_rom) != ROM_SHA1:
            raise ValueError("the staged ROM failed its post-copy hash check")
        temporary.rename(destination)
    except Exception:
        require_private_path(temporary)
        shutil.rmtree(temporary)
        raise
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title-dir", required=True, type=Path, help="locally compiled PPSA##### title folder")
    parser.add_argument("--rom", required=True, type=Path, help="user-owned US big-endian .z64 ROM")
    args = parser.parse_args()
    try:
        destination = stage_title(args.title_dir, args.rom)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"stage_local_title: {error}", file=sys.stderr)
        return 1
    print(f"Private title ready for FTP: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
