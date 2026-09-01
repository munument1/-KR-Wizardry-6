from __future__ import annotations

import struct

import patch_wpcmk_compact_roster as patch


def _target(data: bytes | bytearray, call_at: int) -> int:
    disp = struct.unpack_from("<h", data, call_at + 1)[0]
    return (call_at + 3 + disp) & 0xFFFF


def _synthetic_gender_block(style: int, old_target: int, offset: int) -> bytearray:
    data = bytearray(offset + 32)
    data[offset:offset + 13] = bytes([0xB8, style, 0x00, 0x50]) + bytes.fromhex(
        "8A 46 EC 2A E4 50 FF 76 04"
    )
    data[offset + 13] = 0xE8
    struct.pack_into("<H", data, offset + 14, (old_target - (offset + 16)) & 0xFFFF)
    data[offset + 16:offset + 19] = bytes.fromhex("83 C4 06")
    return data


def test_selected_gender_rewrite_passes_string_pointer_to_wfont0() -> None:
    offset = 0x10
    data = _synthetic_gender_block(7, 0xDD53, offset)
    patch._rewrite_gender(data, offset, 7, 0xDF85, 0xDD53)
    assert data[offset:offset + 11] == bytes.fromhex("B8 07 00 50 8D 46 EC 50 FF 76 04")
    assert _target(data, offset + 11) == 0xDF85
    assert data[offset + 14:offset + 19] == bytes.fromhex("83 C4 06 90 90")


def test_unselected_gender_rewrite_passes_string_pointer_to_gray_renderer() -> None:
    offset = 0x20
    data = _synthetic_gender_block(3, 0xDE7F, offset)
    patch._rewrite_gender(data, offset, 3, 0xDFB9, 0xDE7F)
    assert data[offset:offset + 11] == bytes.fromhex("B8 03 00 50 8D 46 EC 50 FF 76 04")
    assert _target(data, offset + 11) == 0xDFB9


def test_production_wpcmk_contract_constants() -> None:
    assert patch.WPCMK_SIZE == 24793
    assert patch.WPCMK_SHA256 == "e252a526009ad4616dec55981ae6953e9aed54b1824843394e44074b2bf4c59a"
