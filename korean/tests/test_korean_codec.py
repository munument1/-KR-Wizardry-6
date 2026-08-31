#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import korean_codec as k  # noqa: E402


class KoreanCodecTests(unittest.TestCase):
    def test_codebook_frequency_then_codepoint_order(self) -> None:
        book = k.build_codebook(["인간 인간", "간단"])
        self.assertEqual(book.characters[:2], ("간", "인"))

    def test_pair_boundaries(self) -> None:
        chars = tuple(chr(0xAC00 + i) for i in range(129))
        book = k.Codebook(chars)
        self.assertEqual(book.pair_for_index(0), (0x80, 0x80))
        self.assertEqual(book.pair_for_index(127), (0x80, 0xFF))
        self.assertEqual(book.pair_for_index(128), (0x81, 0x80))

    def test_mixed_roundtrip(self) -> None:
        book = k.build_codebook(["인간 전사"])
        text = "인간 HP<0x1F>전사!"
        raw = k.encode_text(text, book)
        self.assertEqual(k.decode_bytes(raw, book, escape_controls=True), text)
        self.assertEqual(k.glyph_count(raw, book), len("인간 HP") + 1 + len("전사!"))

    def test_non_hangul_custom_character_is_supported(self) -> None:
        book = k.build_codebook(["한국어… ×"])
        self.assertIn("…", book.characters)
        self.assertIn("×", book.characters)
        raw = k.encode_text("한국어… ×", book)
        self.assertEqual(k.decode_bytes(raw, book), "한국어… ×")

    def test_high_control_escape_is_reserved(self) -> None:
        book = k.Codebook(("가",))
        with self.assertRaisesRegex(ValueError, "collides"):
            k.encode_text("<0x80>", book)

    def test_unknown_character_rejected(self) -> None:
        book = k.Codebook(("가",))
        with self.assertRaisesRegex(ValueError, "absent"):
            k.encode_text("나", book)

    def test_truncated_pair_rejected(self) -> None:
        book = k.Codebook(("가",))
        with self.assertRaisesRegex(ValueError, "truncated"):
            k.decode_bytes(b"\x80", book)

    def test_runtime_limit_guard(self) -> None:
        # Duplicate validation happens later than the size guard by design.
        with self.assertRaisesRegex(ValueError, "runtime limit"):
            k.Codebook(tuple("가" for _ in range(k.MAX_RUNTIME_GLYPHS + 1)))

    def test_json_roundtrip(self) -> None:
        book = k.Codebook(("가", "나", "다", "…"))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "codebook.json"
            book.save(path)
            loaded = k.Codebook.load(path)
        self.assertEqual(loaded, book)


if __name__ == "__main__":
    unittest.main()
