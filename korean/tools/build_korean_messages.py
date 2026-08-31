#!/usr/bin/env python3
"""Build W6 Korean MSG.DBS/MSG.HDR/MISC.HDR directly from a translation CSV.

The CSV source_text is validated byte-for-byte against the retail message corpus
before any translation is accepted. Non-ASCII translation characters are
encoded with the compact high-bit pair codebook, then the message container is
rebuilt with a full 256-byte Huffman tree and range-safe 1KB bank placement.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from korean_codec import build_codebook, encode_text, glyph_count
from rebuild_message_files import (
    BANK_SIZE,
    build_codes,
    build_records,
    extract_original_messages,
    find_record_start_crossings,
    generate_full_byte_tree,
    load_nodes,
    parse_ranges,
    repack,
    resolve_data_file,
    serialize_nodes,
    validate_built,
)

_ESCAPE_RE = re.compile(r"<0x([0-9A-Fa-f]{2})>")


def unescape_source_text(text: str) -> bytes:
    """Inverse of extract_messages.escape_bytes without importing UI code."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text.startswith("\\\\", i):
            out.append(0x5C)
            i += 2
            continue
        match = _ESCAPE_RE.match(text, i)
        if match:
            out.append(int(match.group(1), 16))
            i = match.end()
            continue
        value = ord(text[i])
        if value > 0x7F:
            raise ValueError(f"non-ASCII literal in source_text: {text[i]!r}")
        out.append(value)
        i += 1
    return bytes(out)


def read_translation_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = list(reader.fieldnames or [])
        required = {"message_id", "translation"}
        if not required.issubset(fields):
            raise ValueError(f"CSV requires columns: {', '.join(sorted(required))}")
        return list(reader), fields


def build_korean_files(
    gamedata: Path,
    translation_csv: Path,
    extra_translation_csv: Path | None = None,
) -> tuple[dict[str, bytes], dict[str, object]]:
    original_misc = resolve_data_file(gamedata, "MISC.HDR").read_bytes()
    original_hdr = resolve_data_file(gamedata, "MSG.HDR").read_bytes()
    original_dbs = resolve_data_file(gamedata, "MSG.DBS").read_bytes()
    original_nodes = load_nodes(original_misc)
    ranges, _ = parse_ranges(original_hdr)
    originals = extract_original_messages(ranges, original_dbs, original_nodes)

    rows, _fields = read_translation_csv(translation_csv)
    by_id: dict[int, dict[str, str]] = {}
    duplicate_ids: list[int] = []
    for row in rows:
        message_id = int(row["message_id"])
        if message_id in by_id:
            duplicate_ids.append(message_id)
        by_id[message_id] = row
    if duplicate_ids:
        raise ValueError(f"duplicate message IDs: {duplicate_ids[:10]}")

    has_source_text = "source_text" in _fields
    missing = sorted(set(originals) - set(by_id)) if has_source_text else []
    extra = sorted(set(by_id) - set(originals))
    if missing or extra:
        raise ValueError(f"CSV ID set mismatch: missing={missing[:10]} extra={extra[:10]}")

    source_mismatches: list[dict[str, object]] = []
    if has_source_text:
        for message_id, original in originals.items():
            try:
                csv_source = unescape_source_text(by_id[message_id]["source_text"])
            except ValueError as exc:
                source_mismatches.append({"message_id": message_id, "error": str(exc)})
                continue
            if csv_source != original:
                source_mismatches.append(
                    {
                        "message_id": message_id,
                        "original_hex": original.hex().upper(),
                        "csv_hex": csv_source.hex().upper(),
                    }
                )
    if source_mismatches:
        raise ValueError(
            f"source_text mismatch in {len(source_mismatches)} rows; first={source_mismatches[0]}"
        )

    translations = [row["translation"] for row in rows if row["translation"] != ""]
    extra_translation_count = 0
    if extra_translation_csv is not None:
        with extra_translation_csv.open("r", encoding="utf-8-sig", newline="") as stream:
            extra_reader = csv.DictReader(stream)
            if "translation" not in (extra_reader.fieldnames or []):
                raise ValueError("extra translation CSV requires a translation column")
            for row in extra_reader:
                value = row["translation"].strip()
                if value:
                    translations.append(value)
                    extra_translation_count += 1
    codebook = build_codebook(translations)
    if len(codebook.characters) > 1024:
        raise ValueError(
            f"unified renderer codebook has {len(codebook.characters)} glyphs; limit is 1024"
        )

    messages: dict[int, bytes] = {}
    overrides: dict[int, bytes] = {}
    longest: list[tuple[int, int, int, str]] = []
    translated_count = 0
    for message_id, original in originals.items():
        translation = by_id.get(message_id, {}).get("translation", "")
        if translation == "":
            encoded = original
        else:
            translated_count += 1
            encoded = encode_text(translation, codebook)
            longest.append((len(encoded), glyph_count(encoded, codebook), message_id, translation))
        messages[message_id] = encoded
        if encoded != original:
            overrides[message_id] = encoded

    nodes = generate_full_byte_tree(messages)
    codes = build_codes(nodes)
    records = build_records(messages, codes)
    output_dbs, output_hdr, padding_bytes = repack(
        ranges,
        records,
        original_hdr,
        keep_range_record_starts_in_bank=True,
    )
    output_misc = serialize_nodes(nodes)
    validate_built(
        ranges,
        output_hdr,
        output_dbs,
        nodes,
        messages,
        require_safe_range_starts=True,
    )
    output_ranges, _ = parse_ranges(output_hdr)
    crossings = find_record_start_crossings(output_ranges, output_dbs)
    if crossings:
        raise AssertionError(f"unexpected record-start crossings: {crossings[:3]}")

    longest.sort(reverse=True)
    files = {
        "MSG.DBS": output_dbs,
        "MSG.HDR": output_hdr,
        "MISC.HDR": output_misc,
    }
    report: dict[str, object] = {
        "source_row_count": len(originals),
        "translation_csv_row_count": len(rows),
        "source_text_validation": has_source_text,
        "source_mismatch_count": 0,
        "translated_row_count": translated_count,
        "changed_message_count": len(overrides),
        "custom_glyph_count": len(codebook.characters),
        "extra_translation_count": extra_translation_count,
        "runtime_glyph_limit": 1024,
        "runtime_glyph_headroom": 1024 - len(codebook.characters),
        "max_encoded_bytes": longest[0][0] if longest else 0,
        "max_logical_glyphs": max((row[1] for row in longest), default=0),
        "longest_rows": [
            {
                "encoded_bytes": byte_len,
                "logical_glyphs": glyphs,
                "message_id": message_id,
                "translation": translation,
            }
            for byte_len, glyphs, message_id, translation in longest[:20]
        ],
        "huffman_byte_codes": len(codes),
        "inter_range_padding_bytes": padding_bytes,
        "msg_dbs_bytes": len(output_dbs),
        "msg_dbs_banks": len(output_dbs) // BANK_SIZE,
        "record_start_bank_crossings": 0,
        "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
    }
    return files, {"report": report, "codebook": codebook, "overrides": overrides}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--translations", type=Path, required=True)
    parser.add_argument("--extra-translations", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    files, metadata = build_korean_files(
        args.gamedata, args.translations, args.extra_translations
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (args.output_dir / name).write_bytes(data)

    codebook = metadata["codebook"]
    codebook.save(args.output_dir / "codebook.json")
    overrides: dict[int, bytes] = metadata["overrides"]
    with (args.output_dir / "message_overrides.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["message_id", "encoded_bytes_hex"])
        for message_id in sorted(overrides):
            writer.writerow([message_id, overrides[message_id].hex().upper()])

    report = metadata["report"]
    (args.output_dir / "build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
