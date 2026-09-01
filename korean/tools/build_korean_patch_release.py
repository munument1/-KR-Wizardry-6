#!/usr/bin/env python3
"""Release entry point for the runtime-tested Wizardry VI Korean build."""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import build_korean_patch as stable
from patch_wpcmk_compact_roster import patch_wpcmk_compact_roster
from scenario_localization import patch_scenario_strings

RELEASE_VERSION = "v0.1.0-alpha.2"
ZIP_FILES = [
    "WROOT.EXE",
    "EGA.DRV",
    "WFONT0.EGA",
    "WBASE.OVR",
    "WPCMK.OVR",
    "SCENARIO.DBS",
    "MSG.DBS",
    "MSG.HDR",
    "MISC.HDR",
    "TITLEPAG.EGA",
    "README_TEST.txt",
    "Galmuri7-OFL.txt",
]

# Full SCENARIO localization: items + monsters + NPCs.
stable.patch_scenario_items = patch_scenario_strings

# Test5, runtime-confirmed: later refresh dispatch could reach the retail DOS
# INT 21h / AX=4CFFh exit trap for valid character-panel cells. Keep the
# black-background/menu routing fixes, but fall back to the normal WFONT0
# refresh path at file offset 0x2E66 instead of terminating the program.
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

# Test6, runtime-safe compact presentation: WBASE race/class fields use the
# same two-glyph boundary as the working character list. The base patch already
# rewrites gender to a full string; race/class are capped at four encoded bytes
# so a two-byte Korean glyph pair is never split.
_stable_make_wbase = stable.make_wbase


def _make_wbase_compact_two_glyphs(original: bytes) -> tuple[bytes, dict[str, object]]:
    built, report = _stable_make_wbase(original)
    patched = bytearray(built)
    for offset, label in (
        (0x1FF3, "roster race compact limit mode 1"),
        (0x2034, "roster class compact limit mode 1"),
        (0x20DC, "roster race compact limit mode 2"),
        (0x2112, "roster class compact limit mode 2"),
    ):
        actual = bytes(patched[offset : offset + 4])
        if actual != b"\x90\x90\x90\x90":
            raise ValueError(f"{label}: expected full-string patch, got {actual.hex(' ')}")
        patched[offset : offset + 4] = bytes.fromhex("C6 46 F0 00")
    report = dict(report)
    report["race_class_compact_bytes"] = 4
    report["race_class_compact_korean_glyphs"] = 2
    return bytes(patched), report


stable.make_wbase = _make_wbase_compact_two_glyphs


def _path_arg(flag: str) -> Path:
    try:
        index = sys.argv.index(flag)
        return Path(sys.argv[index + 1])
    except (ValueError, IndexError) as exc:
        raise ValueError(f"required release argument missing: {flag}") from exc


def _install_wpcmk_patch() -> None:
    game_dir = _path_arg("--game-dir")
    output_dir = _path_arg("--output-dir")
    original = (game_dir / "WPCMK.OVR").read_bytes()
    (output_dir / "WPCMK.OVR").write_bytes(patch_wpcmk_compact_roster(original))


def _refresh_release_readme_and_zip() -> None:
    output_dir = _path_arg("--output-dir")
    zip_path = _path_arg("--zip")
    readme = (
        f"Wizardry VI Korean localization {RELEASE_VERSION}\n\n"
        "1. Back up the original Wizardry VI game folder.\n"
        "2. Extract every file in this ZIP directly into the game folder and overwrite.\n"
        "3. Start the game normally. No script or font installation is required.\n"
        "4. Existing save files are not included or overwritten by this ZIP.\n\n"
        "Includes Korean messages, item/monster/NPC names, and the Korean intro logo.\n"
        "Runtime fixes verified during recovery testing: no black rectangles behind Korean text, "
        "party-member addition no longer restarts the game, portrait/status/rename screens no longer "
        "exit through the DOS error trap, and compact character gender/race/class labels render as "
        "complete two-glyph Korean strings.\n"
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
    _install_wpcmk_patch()
    _refresh_release_readme_and_zip()
    print(f"Release metadata refreshed for {RELEASE_VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
