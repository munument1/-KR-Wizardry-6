from __future__ import annotations

import struct

import build_korean_patch as stable
import build_korean_patch_release as release  # installs production Test5/Test6 runtime wrappers


def _synthetic_wbase() -> bytes:
    data = bytearray(14930)
    for offset, style, call_offset in (
        (0x1FB4, 7, 0x2002),
        (0x209D, 3, 0x20EB),
    ):
        data[offset:offset + 9] = bytes([0xB8, style, 0x00, 0x50]) + bytes.fromhex("8A 46 EC 2A E4")
        data[call_offset] = 0xE8
        struct.pack_into("<h", data, call_offset + 1, 0)
    for offset in (0x1FF3, 0x2034, 0x20DC, 0x2112):
        data[offset:offset + 4] = bytes.fromhex("C6 46 EF 00")
    return bytes(data)


def test_compact_character_info_uses_exactly_two_korean_glyph_pairs() -> None:
    built, report = release._make_wbase_compact_two_glyphs(_synthetic_wbase())

    for offset in (0x1FF3, 0x2034, 0x20DC, 0x2112):
        assert built[offset:offset + 4] == bytes.fromhex("C6 46 F0 00")

    assert report["race_class_compact_bytes"] == 4
    assert report["race_class_compact_korean_glyphs"] == 2


def test_production_release_keeps_test5_safe_refresh_wrapper_installed() -> None:
    assert stable.make_wroot.__name__ == "_make_wroot_with_safe_refresh_fallback"
    assert stable.make_wbase.__name__ == "_make_wbase_compact_two_glyphs"
