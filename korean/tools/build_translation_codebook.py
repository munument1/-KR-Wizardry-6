#!/usr/bin/env python3
"""Build/audit the W6 compact custom-glyph codebook from translation CSVs.

This tool is intentionally CSV-only so translators can work independently of
binary patching. It reads one or more CSV files, collects non-empty values from
``translation`` (configurable), builds a deterministic codebook, and verifies
that every translated MSG row can be encoded within the 255 decoded-byte
fragment limit.

For Scenario/UI CSVs the encoded-byte statistic is still useful, but fixed field
capacity must be checked by the corresponding scenario patcher because those
records have their own per-field limits.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
from korean_codec import Codebook, build_codebook, encode_text, glyph_count, iter_translation_units  # noqa: E402

RUNTIME_GLYPH_LIMIT = 1024


def read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV has no header")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def build_from_csvs(
    paths: list[Path],
    *,
    translation_column: str = "translation",
    id_column: str = "message_id",
) -> tuple[Codebook, dict[str, object]]:
    corpus: list[str] = []
    translated_rows: list[tuple[Path, int, str, str]] = []
    source_row_count = 0

    for path in paths:
        rows, fieldnames = read_csv_rows(path)
        if translation_column not in fieldnames:
            raise ValueError(f"{path}: missing column {translation_column!r}")
        source_row_count += len(rows)
        for row_number, row in enumerate(rows, start=2):
            text = row.get(translation_column, "") or ""
            if text == "":
                continue
            row_id = row.get(id_column, "") if id_column in fieldnames else ""
            corpus.append(text)
            translated_rows.append((path, row_number, row_id, text))

    codebook = build_codebook(corpus)
    encoded_lengths: list[tuple[int, Path, int, str, str]] = []
    glyph_lengths: list[int] = []
    failures: list[dict[str, object]] = []

    for path, row_number, row_id, text in translated_rows:
        try:
            encoded = encode_text(text, codebook)
            encoded_lengths.append((len(encoded), path, row_number, row_id, text))
            glyph_lengths.append(glyph_count(encoded, codebook))
        except ValueError as exc:
            failures.append(
                {
                    "file": str(path),
                    "row": row_number,
                    "id": row_id,
                    "error": str(exc),
                }
            )

    char_frequency: Counter[str] = Counter()
    for text in corpus:
        for unit in iter_translation_units(text):
            if isinstance(unit, str) and ord(unit) > 0x7F:
                char_frequency[unit] += 1

    encoded_lengths.sort(reverse=True, key=lambda item: item[0])
    report: dict[str, object] = {
        "input_files": [str(path) for path in paths],
        "source_row_count": source_row_count,
        "translated_row_count": len(translated_rows),
        "custom_glyph_count": len(codebook.characters),
        "runtime_glyph_limit": RUNTIME_GLYPH_LIMIT,
        "runtime_glyph_headroom": RUNTIME_GLYPH_LIMIT - len(codebook.characters),
        "glyph_limit_exceeded": len(codebook.characters) > RUNTIME_GLYPH_LIMIT,
        "max_encoded_bytes": encoded_lengths[0][0] if encoded_lengths else 0,
        "max_logical_glyphs": max(glyph_lengths, default=0),
        "encoding_failure_count": len(failures),
        "failures": failures,
        "longest_rows": [
            {
                "encoded_bytes": length,
                "file": str(path),
                "row": row_number,
                "id": row_id,
                "translation": text,
            }
            for length, path, row_number, row_id, text in encoded_lengths[:20]
        ],
        "top_custom_characters": [
            {"character": ch, "codepoint": f"U+{ord(ch):04X}", "count": count}
            for ch, count in char_frequency.most_common(50)
        ],
    }
    return codebook, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", nargs="+", type=Path)
    parser.add_argument("--translation-column", default="translation")
    parser.add_argument("--id-column", default="message_id")
    parser.add_argument("--codebook", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    codebook, report = build_from_csvs(
        args.csv,
        translation_column=args.translation_column,
        id_column=args.id_column,
    )
    codebook.save(args.codebook)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in report.items() if k not in {"failures", "longest_rows", "top_custom_characters"}}, ensure_ascii=False, indent=2))
    if report["encoding_failure_count"]:
        return 2
    if report["glyph_limit_exceeded"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
