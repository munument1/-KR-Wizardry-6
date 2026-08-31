#!/usr/bin/env python3
"""Audit translatable fixed strings and residual ASCII in SCENARIO.DBS.

Known structured fields are emitted with exact offsets/capacities.  Remaining
printable runs are reported separately for manual review; they are not assumed
to be user-visible merely because they decode as ASCII.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

ITEM_TABLE_OFFSET = 0x0380
ITEM_RECORD_SIZE = 74
ITEM_SLOT_COUNT = 483
MONSTER_TABLE_OFFSET = 0x154E6
MONSTER_RECORD_SIZE = 222
MONSTER_SLOT_COUNT = 251
NPC_TABLE_OFFSET = 0x22ED0
NPC_RECORD_SIZE = 0x8E
NPC_RECORD_COUNT = 30


def resolve_data_file(gamedata: Path, canonical_name: str) -> Path:
    direct = gamedata / canonical_name
    if direct.exists():
        return direct
    wanted = canonical_name.casefold()
    for child in gamedata.iterdir():
        if child.is_file() and child.name.casefold() == wanted:
            return child
    raise FileNotFoundError(f"Required game data file not found: {canonical_name}")

MONSTER_FIELDS = [
    ("name", 0x02, 16),
    ("name_plural", 0x12, 16),
    ("short_name", 0x22, 16),
    ("short_name_plural", 0x32, 16),
]


def cstring(data: bytes, offset: int, capacity: int) -> str:
    raw = data[offset : offset + capacity]
    raw = raw.split(b"\0", 1)[0]
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return ""


def plausible_text(text: str) -> bool:
    return bool(text) and any(ch.isalpha() for ch in text) and all(
        0x20 <= ord(ch) <= 0x7E for ch in text
    )


def structured_rows(data: bytes) -> tuple[list[dict[str, object]], set[int]]:
    rows: list[dict[str, object]] = []
    claimed: set[int] = set()

    for idx in range(ITEM_SLOT_COUNT):
        off = ITEM_TABLE_OFFSET + idx * ITEM_RECORD_SIZE
        if off + ITEM_RECORD_SIZE > len(data):
            break
        text = cstring(data, off, 16)
        if plausible_text(text):
            rows.append({
                "category": "item", "record_index": idx, "variant": "name",
                "absolute_offset": off, "offset_hex": f"0x{off:05X}",
                "capacity": 16, "source_text": text,
            })
        claimed.update(range(off, min(off + 16, len(data))))

    for idx in range(MONSTER_SLOT_COUNT):
        base = MONSTER_TABLE_OFFSET + idx * MONSTER_RECORD_SIZE
        if base >= len(data):
            break
        for variant, rel, cap in MONSTER_FIELDS:
            off = base + rel
            if off + cap > len(data):
                continue
            text = cstring(data, off, cap)
            if plausible_text(text):
                rows.append({
                    "category": "monster", "record_index": idx, "variant": variant,
                    "absolute_offset": off, "offset_hex": f"0x{off:05X}",
                    "capacity": cap, "source_text": text,
                })
            claimed.update(range(off, min(off + cap, len(data))))

    # 30 fixed-size NPC/special-encounter records immediately follow the
    # monster region.  Each record starts with a 16-byte C string display name.
    # The 0x8E-byte stride is proven by 30 consecutive names and an exact next
    # section boundary at 0x23F74.
    for idx in range(NPC_RECORD_COUNT):
        off = NPC_TABLE_OFFSET + idx * NPC_RECORD_SIZE
        text = cstring(data, off, 16)
        if plausible_text(text):
            rows.append({
                "category": "npc", "record_index": idx, "variant": "name",
                "absolute_offset": off, "offset_hex": f"0x{off:05X}",
                "capacity": 16, "source_text": text,
            })
        claimed.update(range(off, min(off + 16, len(data))))
    return rows, claimed


def residual_runs(data: bytes, claimed: set[int], min_len: int = 4):
    printable = set(range(0x20, 0x7F))
    start = None
    for i, b in enumerate(data):
        ok = b in printable and i not in claimed
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i - start >= min_len:
                yield start, data[start:i].decode("ascii")
            start = None
    if start is not None and len(data) - start >= min_len:
        yield start, data[start:].decode("ascii")


def residual_class(text: str) -> tuple[str, str]:
    # Conservative: simple word shapes remain review candidates only when they
    # contain multiple alphabetic tokens. Numeric/punctuation patterns are
    # overwhelmingly map/stat data in the analyzed retail SCENARIO.DBS.
    words = re.findall(r"[A-Za-z]{3,}", text)
    alpha = sum(ch.isalpha() for ch in text)
    if len(words) >= 2 and alpha / max(len(text), 1) >= 0.65:
        return "REVIEW", "multi-word human-like ASCII outside known fields"
    return "LIKELY_BINARY", "printable binary/map/stat bytes outside known fields"


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gamedata", type=Path, default=Path("gamedata"))
    ap.add_argument("--structured-csv", type=Path)
    ap.add_argument("--residual-csv", type=Path)
    args = ap.parse_args()

    data = resolve_data_file(args.gamedata, "SCENARIO.DBS").read_bytes()
    structured, claimed = structured_rows(data)
    residual = []
    for off, text in residual_runs(data, claimed):
        status, reason = residual_class(text)
        residual.append({
            "absolute_offset": off,
            "offset_hex": f"0x{off:05X}",
            "byte_length": len(text),
            "source_text": text,
            "classification": status,
            "reason": reason,
        })

    from collections import Counter
    c = Counter((r["category"], r["variant"]) for r in structured)
    print(f"structured_total: {len(structured)}")
    for key, value in sorted(c.items()):
        print(f"{key[0]}/{key[1]}: {value}")
    rc = Counter(r["classification"] for r in residual)
    print(f"residual_total: {len(residual)}")
    for key, value in sorted(rc.items()):
        print(f"residual_{key}: {value}")

    if args.structured_csv:
        write_csv(args.structured_csv, structured, [
            "category", "record_index", "variant", "absolute_offset",
            "offset_hex", "capacity", "source_text",
        ])
    if args.residual_csv:
        write_csv(args.residual_csv, residual, [
            "absolute_offset", "offset_hex", "byte_length", "source_text",
            "classification", "reason",
        ])


if __name__ == "__main__":
    main()
