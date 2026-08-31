#!/usr/bin/env python3
from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "fonts"
TOOLS_DIR = ROOT / "tools"
sys.path.insert(0, str(FONT_DIR))
sys.path.insert(0, str(TOOLS_DIR))

import build_galmuri7_bitmap_table as g  # noqa: E402
from korean_codec import Codebook  # noqa: E402


def encode_binary_bitmap(rows: list[list[int]]) -> str:
    """Tiny test-only KBITX encoder using one-pixel black/white runs."""
    data = bytearray((len(rows), len(rows[0])))
    for row in rows:
        for value in row:
            data.append(0x41 if value else 0x01)  # run=1, white or black
    return base64.b64encode(bytes(data)).decode("ascii").rstrip("=")


class GalmuriBuilderTests(unittest.TestCase):
    def test_decode_real_kbitx_style_payload(self) -> None:
        pixels = [[255 if x == y else 0 for x in range(7)] for y in range(7)]
        encoded = encode_binary_bitmap(pixels)
        decoded = g.decode_bitmap(encoded)
        self.assertEqual(decoded, pixels)
        rows = g.to_7x7_rows(decoded)
        self.assertEqual(rows, bytes([0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02]))

    def test_extract_and_build_compact_table(self) -> None:
        chars = ("가", "…")
        book = Codebook(chars)
        diagonal = [[255 if x == y else 0 for x in range(7)] for y in range(7)]
        solid = [[255 for _ in range(7)] for _ in range(7)]
        xml = (
            '<?xml version="1.0"?><font>'
            f'<g u="{ord("가")}" d="{encode_binary_bitmap(diagonal)}"/>'
            f'<g u="{ord("…")}" d="{encode_binary_bitmap(solid)}"/>'
            '</font>'
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mini.kbitx"
            path.write_text(xml, encoding="utf-8")
            rows = g.extract_codebook_rows(path, book)
            table = g.build_compact_table(rows, book)
        self.assertEqual(len(table), 16)
        self.assertEqual(table[:8], bytes.fromhex("80 40 20 10 08 04 02 00"))
        self.assertEqual(table[8:], bytes.fromhex("FE FE FE FE FE FE FE 00"))

    def test_missing_codebook_glyph_rejected(self) -> None:
        book = Codebook(("가", "나"))
        pixels = [[0 for _ in range(7)] for _ in range(7)]
        xml = f'<font><g u="{ord("가")}" d="{encode_binary_bitmap(pixels)}"/></font>'
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "mini.kbitx"
            path.write_text(xml, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing"):
                g.extract_codebook_rows(path, book)


if __name__ == "__main__":
    unittest.main()
