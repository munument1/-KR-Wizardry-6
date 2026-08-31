#!/usr/bin/env python3
"""Release entry point extending the stable renderer build with full SCENARIO localization."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import build_korean_patch as stable
from scenario_localization import patch_scenario_strings

RELEASE_VERSION = "v0.1.0-alpha.2"
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
        "Includes Korean messages, 452 item names, 186 monster records (all visible name variants), "
        "30 NPC names, and the Korean intro logo.\n"
        "SCENARIO fixed-width fields are build-verified at a maximum 15-byte payload.\n"
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
