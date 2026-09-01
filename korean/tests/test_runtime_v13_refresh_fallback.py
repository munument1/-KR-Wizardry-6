from __future__ import annotations

import build_korean_patch as stable
import build_korean_patch_release as release  # noqa: F401 - installs recovery monkeypatch


def _synthetic_wroot() -> bytes:
    data = bytearray(stable.WROOT_SIZE)
    data[0x1D82:0x1D84] = bytes.fromhex("40 02")
    data[0x215A:0x215D] = bytes.fromhex("B9 00 24")
    data[0x2297:0x229A] = bytes.fromhex("B8 00 04")
    data[0x23C7:0x23CA] = bytes.fromhex("B9 00 04")
    data[0x250E:0x251A] = bytes.fromhex("8B 46 08 8A E0 B1 04 D2 E4 8A 46 06")
    data[0x26E9:0x26F2] = bytes.fromhex("55 8B EC 83 EC 04 56 06 1E")
    data[0x26FB:0x2707] = bytes.fromhex("8B 5E FE FF 46 FE 8A 07 32 E4 0A C0")
    data[0x271D:0x2726] = bytes.fromhex("55 8B EC 83 EC 04 56 06 1E")
    data[0x2E69:0x2E6E] = bytes.fromhex("2E FF 1E 8A 1B")
    return bytes(data)


def test_unexpected_refresh_font_falls_back_instead_of_entering_exit_trap() -> None:
    built, report = stable.make_wroot(_synthetic_wroot(), font_size=9160, driver_size=17207)

    # 0x2E48 used to be EB 02, which falls into the retail INT 21h / 4CFFh
    # termination block at 0x2E4C. EB 1C jumps to the normal WFONT0 refresh
    # path at 0x2E66 while preserving the newer custom-menu dispatch above it.
    assert built[0x2E48:0x2E4A] == bytes.fromhex("EB 1C")
    assert built[0x2E31:0x2E48] == bytes.fromhex(
        "8B 07 A8 80 74 07 F6 C4 08 75 20 EB 28 "
        "F6 C4 0F 74 23 80 FC 04 76 14"
    )
    assert report["refresh_invalid_font_fallback"] == "WFONT0 refresh path at file 0x2E66"
