from pathlib import Path

import pytest

from scenario_localization import (
    ITEM_TABLE_OFFSET,
    MONSTER_RECORD_SIZE,
    MONSTER_TABLE_OFFSET,
    NPC_RECORD_SIZE,
    NPC_TABLE_OFFSET,
    encode_compact_text,
    field_offset,
    load_translation_rows,
)


def test_field_offsets_match_reverse_engineered_layout():
    assert field_offset("item", 0, "name") == ITEM_TABLE_OFFSET
    assert field_offset("monster", 3, "name") == MONSTER_TABLE_OFFSET + 3 * MONSTER_RECORD_SIZE + 0x02
    assert field_offset("monster", 3, "name_plural") == MONSTER_TABLE_OFFSET + 3 * MONSTER_RECORD_SIZE + 0x12
    assert field_offset("monster", 3, "short_name") == MONSTER_TABLE_OFFSET + 3 * MONSTER_RECORD_SIZE + 0x22
    assert field_offset("monster", 3, "short_name_plural") == MONSTER_TABLE_OFFSET + 3 * MONSTER_RECORD_SIZE + 0x32
    assert field_offset("npc", 29, "name") == NPC_TABLE_OFFSET + 29 * NPC_RECORD_SIZE


def test_field_offsets_reject_unsupported_fields():
    with pytest.raises(ValueError):
        field_offset("item", 483, "name")
    with pytest.raises(ValueError):
        field_offset("monster", 0, "nickname")
    with pytest.raises(ValueError):
        field_offset("npc", 30, "name")


def test_compact_codec_preserves_ascii_and_encodes_codebook_pairs():
    assert encode_compact_text("A가B", ["가"]) == b"A\x80\x80B"


def test_compact_codec_rejects_missing_glyph():
    with pytest.raises(ValueError, match="unified codebook"):
        encode_compact_text("나", ["가"])


def test_translation_loader_accepts_compact_monster_rows(tmp_path: Path):
    path = tmp_path / "scenario.csv"
    path.write_text(
        "category,record_index,variant,translation\n"
        "monster,0,name,쥐\n"
        "npc,0,name,코스믹포지\n",
        encoding="utf-8",
    )
    rows = load_translation_rows(path)
    assert rows[("monster", 0, "name")] == "쥐"
    assert rows[("npc", 0, "name")] == "코스믹포지"


def test_translation_loader_rejects_duplicate_keys(tmp_path: Path):
    path = tmp_path / "scenario.csv"
    path.write_text(
        "category,record_index,variant,translation\n"
        "monster,0,name,쥐\n"
        "monster,0,name,랫\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_translation_rows(path)
