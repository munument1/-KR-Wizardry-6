from __future__ import annotations

import hashlib
import struct

WPCMK_SIZE = 24793
WPCMK_SHA256 = "e252a526009ad4616dec55981ae6953e9aed54b1824843394e44074b2bf4c59a"


def _call_target16(data: bytes | bytearray, call_at: int) -> int:
    if data[call_at] != 0xE8:
        raise ValueError(f"expected near call at 0x{call_at:X}")
    disp = struct.unpack_from("<h", data, call_at + 1)[0]
    return (call_at + 3 + disp) & 0xFFFF


def _rewrite_gender(patched: bytearray, offset: int, style: int, string_target: int, old_target: int) -> None:
    old = bytes(patched[offset : offset + 19])
    if old[:4] != bytes([0xB8, style, 0x00, 0x50]) or old[4:9] != bytes.fromhex("8A 46 EC 2A E4"):
        raise ValueError(f"gender signature mismatch at 0x{offset:X}")
    if _call_target16(patched, offset + 13) != old_target:
        raise ValueError(f"gender call target mismatch at 0x{offset:X}")

    replacement = bytearray(bytes([0xB8, style, 0x00, 0x50]))
    replacement += bytes.fromhex("8D 46 EC 50 FF 76 04 E8 00 00 83 C4 06 90 90")
    call_at = offset + 11
    struct.pack_into("<H", replacement, 12, (string_target - (call_at + 3)) & 0xFFFF)
    patched[offset : offset + 19] = replacement


def patch_wpcmk_compact_roster(original: bytes) -> bytes:
    if len(original) != WPCMK_SIZE:
        raise ValueError("unexpected WPCMK.OVR size")
    if hashlib.sha256(original).hexdigest() != WPCMK_SHA256:
        raise ValueError("unexpected WPCMK.OVR SHA-256")

    patched = bytearray(original)

    # Highlighted row: preserve WFONT0 colors, but pass the whole Korean gender string.
    _rewrite_gender(patched, 0x5511, 7, 0xDF85, 0xDD53)
    # Non-highlighted rows: preserve the gray WFONT1..4 path, but pass a string pointer.
    _rewrite_gender(patched, 0x55FA, 3, 0xDFB9, 0xDE7F)

    # Retail truncates race/class after 3 bytes. Korean uses 2-byte glyph pairs,
    # so terminate after 4 bytes = exactly two Korean glyphs.
    for offset in (0x5550, 0x5591, 0x5639, 0x566F):
        if bytes(patched[offset : offset + 4]) != bytes.fromhex("C6 46 EF 00"):
            raise ValueError(f"race/class signature mismatch at 0x{offset:X}")
        patched[offset : offset + 4] = bytes.fromhex("C6 46 F0 00")

    result = bytes(patched)
    if _call_target16(result, 0x551C) != 0xDF85:
        raise AssertionError("selected gender string target mismatch")
    if _call_target16(result, 0x5605) != 0xDFB9:
        raise AssertionError("unselected gender string target mismatch")
    return result
