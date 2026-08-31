#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import audit_text_renderer as a  # noqa: E402


class TextRendererAuditTests(unittest.TestCase):
    def test_longest_zero_run(self) -> None:
        data = b"XX\0\0Y\0\0\0\0Z"
        self.assertEqual(a.longest_zero_run(data), (5, 9))

    def test_cs_file_relationship(self) -> None:
        # Retail WROOT has a 0x200-byte MZ header.  The audited WFONT0 string
        # loop at file 0x26E9 is therefore load-module CS:0x24E9.
        self.assertEqual(0x26E9 - a.EXPECTED_MZ_HEADER, 0x24E9)
        self.assertEqual(0x271D - a.EXPECTED_MZ_HEADER, 0x251D)


if __name__ == "__main__":
    unittest.main()
