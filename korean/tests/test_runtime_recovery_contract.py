from __future__ import annotations

import struct

import build_korean_patch as patch
import build_korean_patch_release as release  # noqa: F401 - installs production runtime wrappers


def _synthetic_wroot() -> bytes:
    data = bytearray(patch.WROOT_SIZE)
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


def _synthetic_ega() -> bytes:
    data = bytearray(patch.EGA_SIZE)
    data[0x1A7:0x1BA] = bytes.fromhex(
        "8A D8 32 FF B1 03 D3 E3 2E 8B 16 55 01 89 56 FE 89 5E FC"
    )
    entry1 = bytes.fromhex(
        "8A D8 32 FF B1 05 D3 E3 8B F3 2E 8B 16 59 01 FE CC 74 17 "
        "2E 8B 16 5D 01 FE CC 74 0E 2E 8B 16 61 01 FE CC 74 05 "
        "2E 8B 16 65 01 8E DA"
    )
    data[0x444:0x444 + len(entry1)] = entry1
    return bytes(data)


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


def test_wfont0_pair_loop_preserves_source_pointer_and_stack_contract() -> None:
    built, report = patch.make_wroot(_synthetic_wroot(), font_size=9160, driver_size=17207)

    assert built[0x26E9:0x26F6] == bytes.fromhex(
        "55 8B EC 56 57 06 1E 8B 76 04 8B 7E 06"
    )
    assert bytes.fromhex("83 C4 06 EB DF 1F 07 5F 5E 5D C3") in built[0x26E9:0x271D]
    assert report["pair_draw_call_target_cs"] == "0x22B7"
    assert report["overlay_zero_window_used"] is False


def test_refresh_keeps_menu_identity_and_uses_test5_safe_fallback() -> None:
    built, report = patch.make_wroot(_synthetic_wroot(), font_size=9160, driver_size=17207)
    assert built[0x2E31:0x2E4C] == bytes.fromhex(
        "8B 07 A8 80 74 07 F6 C4 08 75 20 EB 28 "
        "F6 C4 0F 74 23 80 FC 04 76 14 EB 1C 90 90"
    )
    assert report["menu_custom_cell_sentinel"] == "AH bit 3"
    assert report["refresh_invalid_font_fallback"] == "WFONT0 refresh path at file 0x2E66"

    ega, ega_report = patch.make_ega(_synthetic_ega(), glyph_table=b"\xAA" * 16)
    assert ega_report["wfont0_background_mode"].startswith("retail four-plane renderer")
    assert ega_report["entry0_call_target_com"] == ega_report["custom_helper_com"]
    assert ega_report["entry1_call_target_com"] == ega_report["menu_helper_com"]
    assert len(ega) > patch.EGA_SIZE


def test_compact_wbase_uses_complete_two_glyph_pairs() -> None:
    built, report = patch.make_wbase(_synthetic_wbase())
    for offset in (0x1FF3, 0x2034, 0x20DC, 0x2112):
        assert built[offset:offset + 4] == bytes.fromhex("C6 46 F0 00")
    assert report["full_gender_strings"] is True
    assert report["race_three_byte_truncation_removed"] is True
    assert report["class_three_byte_truncation_removed"] is True
    assert report["race_class_compact_bytes"] == 4
    assert report["race_class_compact_korean_glyphs"] == 2
