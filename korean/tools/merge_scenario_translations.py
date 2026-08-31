#!/usr/bin/env python3
"""Merge committed Wizardry VI SCENARIO translation tables for a release build."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

FIELDS = ["category", "record_index", "variant", "translation"]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(FIELDS).issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: missing required columns")
        return [{key: row[key] for key in FIELDS} for row in reader]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--actors", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = read_rows(args.items) + read_rows(args.actors)
    seen: set[tuple[str, int, str]] = set()
    for row in rows:
        key = (
            row["category"].strip().lower(),
            int(row["record_index"]),
            row["variant"].strip().lower(),
        )
        if key in seen:
            raise ValueError(f"duplicate SCENARIO key: {key}")
        seen.add(key)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    counts: dict[tuple[str, str], int] = {}
    for category, _record_index, variant in seen:
        counts[(category, variant)] = counts.get((category, variant), 0) + 1
    print({"rows": len(rows), "counts": dict(sorted(counts.items()))})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
