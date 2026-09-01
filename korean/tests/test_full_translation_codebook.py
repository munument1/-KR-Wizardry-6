#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys

TOOLS = Path(__file__).resolve().parents[1] / "tools"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TOOLS))

import build_translation_codebook as b  # noqa: E402


def test_full_translation_corpus_fits_runtime_codebook():
    paths = [
        ROOT / "korean/translation/messages_ko.csv",
        ROOT / "korean/translation/scenario_items_ko.csv",
        ROOT / "korean/translation/scenario_monsters_ko.csv",
    ]
    book, report = b.build_from_csvs(paths)
    assert report["encoding_failure_count"] == 0
    assert len(book.characters) <= b.RUNTIME_GLYPH_LIMIT
    assert report["runtime_glyph_headroom"] >= 0


def test_scenario_translation_row_counts():
    _book, report = b.build_from_csvs(
        [
            ROOT / "korean/translation/scenario_items_ko.csv",
            ROOT / "korean/translation/scenario_monsters_ko.csv",
        ]
    )
    # Full SCENARIO coverage is explicit after the final QA pass:
    # 452 item names + 741 monster fields + 30 NPC names.
    assert report["source_row_count"] == 1223
    assert report["translated_row_count"] == 1223
