#!/usr/bin/env python3
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import rebuild_message_files as rm  # noqa: E402


def record(total_bytes: int) -> bytes:
    if not 2 <= total_bytes <= 256:
        raise ValueError(total_bytes)
    return bytes([total_bytes - 1]) + bytes(total_bytes - 1)


class MessageRepackSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ranges = [
            rm.Range(100, 2, 0, 0),
            rm.Range(200, 2, 0, 0),
        ]
        self.records = {
            100: record(250),
            101: record(250),
            102: record(250),
            200: record(200),
            201: record(200),
            202: record(200),
        }
        words = [2, 100, 0, 2, 200, 0, 2]
        self.hdr = struct.pack(f"<{len(words)}H", *words)

    def test_safe_repack_moves_range_start_to_next_bank(self) -> None:
        dbs, hdr, padding = rm.repack(
            self.ranges,
            self.records,
            self.hdr,
            keep_range_record_starts_in_bank=True,
        )
        parsed, _ = rm.parse_ranges(hdr)
        self.assertEqual((parsed[0].bank, parsed[0].bank_offset), (0, 0))
        self.assertEqual((parsed[1].bank, parsed[1].bank_offset), (1, 0))
        self.assertEqual(padding, 1024 - 750)
        self.assertEqual(rm.find_record_start_crossings(parsed, dbs), [])

    def test_unsafe_sequential_layout_exposes_crossing(self) -> None:
        dbs, hdr, padding = rm.repack(
            self.ranges,
            self.records,
            self.hdr,
            keep_range_record_starts_in_bank=False,
        )
        parsed, _ = rm.parse_ranges(hdr)
        self.assertEqual(padding, 0)
        violations = rm.find_record_start_crossings(parsed, dbs)
        self.assertTrue(any(message_id == 202 for _, message_id, _, _ in violations))


if __name__ == "__main__":
    unittest.main()
