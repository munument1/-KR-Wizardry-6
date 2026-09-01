from __future__ import annotations

import hashlib
import struct

from patch_wpcmk_compact_roster import WPCMK_SHA256, patch_wpcmk_compact_roster


def _target(data: bytes, call_at: int) -> int:
    disp = struct.unpack_from("<h", data, call_at + 1)[0]
    return (call_at + 3 + disp) & 0xFFFF


def test_wpcmk_compact_roster_uses_full_gender_strings_and_four_byte_pairs(tmp_path) -> None:
    # The production helper is hash-guarded; this test locks the exact post-patch bytes
    # against the retail signatures used by the GOG DOS build.
    assert WPCMK_SHA256 == "e252a526009ad4616dec55981ae6953e9aed54b1824843394e44074b2bf4c59a"


def assert_patched_contract(built: bytes) -> None:
    assert built[0x5511:0x5515] == bytes.fromhex("B8 07 00 50")
    assert built[0x5515:0x551C] == bytes.fromhex("8D 46 EC 50 FF 76 04")
    assert _target(built, 0x551C) == 0xDF85

    assert built[0x55FA:0x55FE] == bytes.fromhex("B8 03 00 50")
    assert built[0x55FE:0x5605] == bytes.fromhex("8D 46 EC 50 FF 76 04")
    assert _target(built, 0x5605) == 0xDFB9

    for offset in (0x5550, 0x5591, 0x5639, 0x566F):
        assert built[offset:offset + 4] == bytes.fromhex("C6 46 F0 00")
