#!/usr/bin/env python3
"""Extract curated fixed-ID system text tables from Wizardry VI MSG.DBS.

Many names that look like SCENARIO data (races, classes, skills and spells) are
actually stored as ordinary message IDs.  This tool layers a conservative
semantic index over the lossless MSG extractor without duplicating or changing
the underlying message representation.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from extract_messages import extract

# Only ranges with clear contiguous semantics are promoted here.  Narrative
# dialogue and one-off UI prose remain in the normal Messages table.
TABLE_SPECS: list[tuple[str, list[int]]] = [
    ("race", list(range(100, 111))),
    ("class", list(range(120, 134))),
    ("gender", [140, 141]),
    ("character_stat", list(range(200, 218))),
    ("main_action", list(range(301, 313))),
    ("equipment_slot", list(range(351, 360))),
    ("item_effect_label", list(range(465, 478))),
    ("skill_category", list(range(600, 604))),
    ("spell_school", list(range(704, 708))),
    ("class_rank_title", list(range(800, 940))),
    ("combat_status", list(range(3471, 3499))),
    ("spell", list(range(4000, 4082))),
    ("skill", list(range(5500, 5530))),
]


def build_rows(gamedata: Path) -> list[dict[str, object]]:
    messages, _stats = extract(gamedata)
    by_id = {int(row["message_id"]): row for row in messages}
    out: list[dict[str, object]] = []
    seen: set[int] = set()

    for category, ids in TABLE_SPECS:
        for message_id in ids:
            row = by_id.get(message_id)
            if row is None or not str(row["source_text"]):
                continue
            if message_id in seen:
                raise ValueError(f"message ID {message_id} appears in more than one system table")
            seen.add(message_id)
            out.append(
                {
                    "category": category,
                    "message_id": message_id,
                    "source_text": row["source_text"],
                    "range_index": row["range_index"],
                    "bank": row["bank"],
                    "bank_offset": row["bank_offset"],
                    "record_length": row["record_length"],
                }
            )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    args = parser.parse_args()

    rows = build_rows(args.gamedata)
    counts: dict[str, int] = {}
    for row in rows:
        category = str(row["category"])
        counts[category] = counts.get(category, 0) + 1

    print(f"Structured MSG system entries: {len(rows)}")
    for category in sorted(counts):
        print(f"  {category}: {counts[category]}")

    if args.csv:
        args.csv.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "category", "message_id", "source_text", "range_index",
            "bank", "bank_offset", "record_length",
        ]
        with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
