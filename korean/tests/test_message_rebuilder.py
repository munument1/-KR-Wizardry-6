#!/usr/bin/env python3
"""Pure unit tests for the Wizardry VI message container rebuilder.

These tests do not require or embed retail game data.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import rebuild_message_files as r  # noqa: E402


class MessageRebuilderTests(unittest.TestCase):
    def test_empty_message_uses_retail_canonical_record(self) -> None:
        nodes = r.generate_full_byte_tree({1: b""})
        records = r.build_records({1: b""}, r.build_codes(nodes))
        self.assertEqual(records[1], b"\x01\x00")

    def test_generated_tree_exposes_all_256_byte_values(self) -> None:
        nodes = r.generate_full_byte_tree({1: b"ABC"})
        self.assertEqual(len(nodes), 256)
        codes = r.build_codes(nodes)
        self.assertEqual(set(codes), set(range(256)))

    def test_all_byte_values_encode_and_decode_in_safe_fragments(self) -> None:
        messages = {
            100 + i: bytes(range(i * 64, (i + 1) * 64))
            for i in range(4)
        }
        nodes = r.generate_full_byte_tree(messages)
        codes = r.build_codes(nodes)
        for message_id, raw in messages.items():
            compressed = r.encode(codes, raw)
            self.assertEqual(r.decode(nodes, compressed, len(raw)), raw, message_id)

    def test_repack_can_preserve_unreferenced_identity_tail(self) -> None:
        ranges = [r.Range(start_id=100, id_span=1, bank=0, bank_offset=0)]
        records = {100: b"\x01\x00", 101: b"\x01\x00"}
        template = bytes((i * 37) & 0xFF for i in range(r.BANK_SIZE))
        dbs, hdr = r.repack(
            ranges,
            records,
            original_hdr=b"",
            preserve_tail_from=template,
        )
        self.assertEqual(dbs[:4], b"\x01\x00\x01\x00")
        self.assertEqual(dbs[4:], template[4:])
        parsed, _ = r.parse_ranges(hdr)
        self.assertEqual((parsed[0].start_id, parsed[0].bank, parsed[0].bank_offset), (100, 0, 0))

    def test_decoded_length_over_255_is_rejected(self) -> None:
        messages = {1: bytes(range(256))}
        nodes = r.generate_full_byte_tree(messages)
        with self.assertRaisesRegex(ValueError, "decoded length 256 exceeds 255"):
            r.build_records(messages, r.build_codes(nodes))

    def test_compressed_payload_over_255_is_rejected(self) -> None:
        # With an all-symbol equal-frequency tree, each byte takes 8 bits.  A
        # 255-byte message therefore needs 255 compressed bytes + one decoded
        # length byte, which cannot fit in record_len.
        nodes = r.generate_full_byte_tree({})
        raw = bytes(range(255))
        with self.assertRaisesRegex(ValueError, "compressed payload 256 exceeds 255"):
            r.build_records({1: raw}, r.build_codes(nodes))


if __name__ == "__main__":
    unittest.main()
