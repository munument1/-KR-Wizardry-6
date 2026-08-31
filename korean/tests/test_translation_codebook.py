#!/usr/bin/env python3
from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))

import build_translation_codebook as b  # noqa: E402


class TranslationCodebookTests(unittest.TestCase):
    def test_csv_corpus_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "messages.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["message_id", "source_text", "translation"])
                writer.writeheader()
                writer.writerow({"message_id": "100", "source_text": "HUMAN", "translation": "인간"})
                writer.writerow({"message_id": "101", "source_text": "ELF", "translation": "엘프…"})
                writer.writerow({"message_id": "102", "source_text": "EMPTY", "translation": ""})
            book, report = b.build_from_csvs([path])
        self.assertIn("…", book.characters)
        self.assertEqual(report["source_row_count"], 3)
        self.assertEqual(report["translated_row_count"], 2)
        self.assertEqual(report["encoding_failure_count"], 0)
        self.assertGreater(report["custom_glyph_count"], 0)


if __name__ == "__main__":
    unittest.main()
