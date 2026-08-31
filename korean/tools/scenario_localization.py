#!/usr/bin/env python3
"""Patch Korean item, monster, and NPC display names in Wizardry VI SCENARIO.DBS."""
from __future__ import annotations

import csv
import hashlib
from collections import Counter
from pathlib import Path

SCENARIO_SHA256 = "6e5a87ca30864406f7422b3685b4f31df6683b2b6fae93b7e29d59a9a8da32dd"
ITEM_TABLE_OFFSET = 0x0380
ITEM_RECORD_SIZE = 74
ITEM_SLOT_COUNT = 483
MONSTER_TABLE_OFFSET = 0x154E6
MONSTER_RECORD_SIZE = 222
MONSTER_SLOT_COUNT = 251
NPC_TABLE_OFFSET = 0x22ED0
NPC_RECORD_SIZE = 0x8E
NPC_RECORD_COUNT = 30
FIELD_BYTES = 16
MAX_PAYLOAD_BYTES = FIELD_BYTES - 1

MONSTER_FIELDS = {
    "name": 0x02,
    "name_plural": 0x12,
    "short_name": 0x22,
    "short_name_plural": 0x32,
}
EXPECTED_RETAIL_FIELDS = {
    ("item", "name"): 452,
    ("monster", "name"): 186,
    ("monster", "name_plural"): 185,
    ("monster", "short_name"): 185,
    ("monster", "short_name_plural"): 185,
    ("npc", "name"): 30,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def encode_compact_text(text: str, characters: list[str]) -> bytes:
    index = {ch: i for i, ch in enumerate(characters)}
    out = bytearray()
    for ch in text:
        value = ord(ch)
        if value < 0x80:
            out.append(value)
            continue
        if ch not in index:
            raise ValueError(f"character is not present in the unified codebook: {ch!r}")
        glyph_index = index[ch]
        if glyph_index >= 1024:
            raise ValueError(f"glyph index exceeds runtime limit: {glyph_index}")
        out.extend((0x80 + glyph_index // 128, 0x80 + glyph_index % 128))
    return bytes(out)


def _source_field(original: bytes, offset: int) -> bytes:
    raw = original[offset : offset + FIELD_BYTES]
    if len(raw) != FIELD_BYTES:
        raise ValueError(f"SCENARIO field outside file at 0x{offset:X}")
    value = raw.split(b"\0", 1)[0]
    if not value:
        return b""
    if any(byte < 0x20 or byte > 0x7E for byte in value):
        raise ValueError(f"SCENARIO source field is not retail ASCII at 0x{offset:X}: {value.hex()}")
    return value


def field_offset(category: str, record_index: int, variant: str) -> int:
    if category == "item":
        if variant != "name" or not 0 <= record_index < ITEM_SLOT_COUNT:
            raise ValueError(f"invalid item field: index={record_index} variant={variant!r}")
        return ITEM_TABLE_OFFSET + record_index * ITEM_RECORD_SIZE
    if category == "monster":
        if variant not in MONSTER_FIELDS or not 0 <= record_index < MONSTER_SLOT_COUNT:
            raise ValueError(f"invalid monster field: index={record_index} variant={variant!r}")
        return MONSTER_TABLE_OFFSET + record_index * MONSTER_RECORD_SIZE + MONSTER_FIELDS[variant]
    if category == "npc":
        if variant != "name" or not 0 <= record_index < NPC_RECORD_COUNT:
            raise ValueError(f"invalid NPC field: index={record_index} variant={variant!r}")
        return NPC_TABLE_OFFSET + record_index * NPC_RECORD_SIZE
    raise ValueError(f"unsupported SCENARIO category: {category!r}")


def enumerate_retail_fields(original: bytes) -> dict[tuple[str, int, str], bytes]:
    fields: dict[tuple[str, int, str], bytes] = {}
    for index in range(ITEM_SLOT_COUNT):
        key = ("item", index, "name")
        value = _source_field(original, field_offset(*key))
        if value:
            fields[key] = value
    for index in range(MONSTER_SLOT_COUNT):
        for variant in MONSTER_FIELDS:
            key = ("monster", index, variant)
            value = _source_field(original, field_offset(*key))
            if value:
                fields[key] = value
    for index in range(NPC_RECORD_COUNT):
        key = ("npc", index, "name")
        value = _source_field(original, field_offset(*key))
        if value:
            fields[key] = value
    return fields


def load_translation_rows(path: Path) -> dict[tuple[str, int, str], str]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"category", "record_index", "variant", "translation"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"SCENARIO CSV requires columns: {', '.join(sorted(required))}")
        rows: dict[tuple[str, int, str], str] = {}
        for line_no, row in enumerate(reader, 2):
            category = row["category"].strip().lower()
            variant = row["variant"].strip().lower()
            record_index = int(row["record_index"])
            translation = row["translation"].strip()
            key = (category, record_index, variant)
            field_offset(*key)
            if key in rows:
                raise ValueError(f"duplicate SCENARIO translation at line {line_no}: {key}")
            if not translation:
                raise ValueError(f"empty SCENARIO translation at line {line_no}: {key}")
            rows[key] = translation
    return rows


def patch_scenario_strings(
    original: bytes, translation_csv: Path, characters: list[str]
) -> tuple[bytes, dict[str, object]]:
    if sha256(original) != SCENARIO_SHA256:
        raise ValueError("SCENARIO.DBS SHA-256 mismatch; expected the supported GOG/DOS retail file")

    retail = enumerate_retail_fields(original)
    retail_counts = Counter((category, variant) for category, _index, variant in retail)
    if dict(retail_counts) != EXPECTED_RETAIL_FIELDS:
        raise ValueError(
            "SCENARIO retail field layout changed: "
            f"actual={dict(sorted(retail_counts.items()))} expected={EXPECTED_RETAIL_FIELDS}"
        )

    translations = load_translation_rows(translation_csv)

    def resolved_translation(key: tuple[str, int, str]) -> str | None:
        if key in translations:
            return translations[key]
        category, record_index, variant = key
        if category == "monster" and variant != "name":
            return translations.get(("monster", record_index, "name"))
        return None

    missing = sorted(key for key in retail if resolved_translation(key) is None)
    extra = sorted(set(translations) - set(retail))
    if missing or extra:
        raise ValueError(f"SCENARIO translation coverage mismatch: missing={missing[:8]} extra={extra[:8]}")

    patched = bytearray(original)
    encoded_lengths: list[int] = []
    translated_counts: Counter[tuple[str, str]] = Counter()
    for key in sorted(retail):
        translation = resolved_translation(key)
        if translation is None:
            raise AssertionError(f"unresolved SCENARIO translation: {key}")
        encoded = encode_compact_text(translation, characters)
        if b"\0" in encoded:
            raise ValueError(f"SCENARIO translation contains NUL: {key}")
        if not 1 <= len(encoded) <= MAX_PAYLOAD_BYTES:
            raise ValueError(
                f"SCENARIO translation exceeds {MAX_PAYLOAD_BYTES} encoded bytes: "
                f"{key} {translation!r} -> {len(encoded)}"
            )
        offset = field_offset(*key)
        patched[offset : offset + FIELD_BYTES] = encoded + b"\0" * (FIELD_BYTES - len(encoded))
        if patched[offset : offset + len(encoded)] != encoded or patched[offset + len(encoded)] != 0:
            raise AssertionError(f"SCENARIO write verification failed: {key}")
        encoded_lengths.append(len(encoded))
        translated_counts[(key[0], key[2])] += 1

    unchanged = []
    for key, source in retail.items():
        offset = field_offset(*key)
        current = bytes(patched[offset : offset + FIELD_BYTES]).split(b"\0", 1)[0]
        if current == source:
            unchanged.append(key)
    if unchanged:
        raise AssertionError(f"retail ASCII SCENARIO fields survived patching: {unchanged[:8]}")

    return bytes(patched), {
        "source_sha256": sha256(original),
        "translation_csv": str(translation_csv),
        "translation_rows": len(translations),
        "translated_fields": sum(translated_counts.values()),
        "translated_item_names": translated_counts[("item", "name")],
        "translated_monster_names": translated_counts[("monster", "name")],
        "translated_monster_plural_names": translated_counts[("monster", "name_plural")],
        "translated_monster_short_names": translated_counts[("monster", "short_name")],
        "translated_monster_short_plural_names": translated_counts[("monster", "short_name_plural")],
        "translated_npc_names": translated_counts[("npc", "name")],
        "field_bytes": FIELD_BYTES,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "max_encoded_name_bytes": max(encoded_lengths, default=0),
        "retail_ascii_fields_remaining": 0,
    }
