#!/usr/bin/env python3
"""Release entry point extending the stable renderer build with full SCENARIO localization."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import build_korean_patch as stable
from scenario_localization import patch_scenario_strings

RELEASE_VERSION = "v0.1.0-alpha.2-recovery"
ZIP_FILES = [
    "WROOT.EXE",
    "EGA.DRV",
    "WFONT0.EGA",
    "WBASE.OVR",
    "SCENARIO.DBS",
    "MSG.DBS",
    "MSG.HDR",
    "MISC.HDR",
    "TITLEPAG.EGA",
    "README_TEST.txt",
    "Galmuri7-OFL.txt",
]

# Keep the runtime-tested WFONT0/WFONT1..4 renderer implementation byte-for-byte
# in build_korean_patch.py. Only replace its SCENARIO patch callback.
stable.patch_scenario_items = patch_scenario_strings

# v13 runtime comparison found that the later refresh split can reach the
# retail DOS exit/error trap immediately after 0x2E4B when an otherwise valid
# cell carries AH > 4. The character portrait/status/rename screens exercise
# such cells. Preserve the later custom-menu/background routing, but make the
# final unsupported-font branch fall back to the normal WFONT0 refresh path at
# file offset 0x2E66 instead of entering the exit trap at 0x2E4C.
_stable_make_wroot = stable.make_wroot


def _make_wroot_with_safe_refresh_fallback(
    original: bytes, font_size: int, driver_size: int
) -> tuple[bytes, dict[str, object]]:
    built, report = _stable_make_wroot(original, font_size, driver_size)
    patched = bytearray(built)
    if bytes(patched[0x2E48:0x2E4A]) != bytes.fromhex("EB 02"):
        raise ValueError("refresh unsupported-font branch signature mismatch")
    patched[0x2E48:0x2E4A] = bytes.fromhex("EB 1C")
    report = dict(report)
    report["refresh_invalid_font_fallback"] = "WFONT0 refresh path at file 0x2E66"
    return bytes(patched), report


stable.make_wroot = _make_wroot_with_safe_refresh_fallback


def _path_arg(flag: str) -> Path:
    try:
        index = sys.argv.index(flag)
        return Path(sys.argv[index + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"required release argument missing: {flag}") from exc


def _refresh_release_readme_and_zip() -> None:
    output_dir = _path_arg("--output-dir")
    zip_path = _path_arg("--zip")
    readme = (
        f"Wizardry VI Korean localization {RELEASE_VERSION}\n\n"
        "1. Back up the original Wizardry VI game folder.\n"
        "2. Extract every file in this ZIP directly into the game folder and overwrite.\n"
        "3. Start the game normally. No script or font installation is required.\n"
        "4. Existing save files are not included or overwritten by this ZIP.\n\n"
        "Recovery build: preserves the later black-background and party-add fixes, "
        "while routing unexpected refresh font/style cells away from the DOS exit trap.\n"
        "Please test portrait selection, character review/status, and rename first.\n"
    )
    (output_dir / "README_TEST.txt").write_text(readme, encoding="utf-8", newline="\r\n")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ZIP_FILES:
            path = output_dir / name
            if not path.is_file():
                raise FileNotFoundError(f"release output missing: {path}")
            archive.write(path, arcname=name)


def main() -> int:
    result = stable.main()
    if result != 0:
        return result
    _refresh_release_readme_and_zip()
    print(f"Release metadata refreshed for {RELEASE_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
