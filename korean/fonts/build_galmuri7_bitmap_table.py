#!/usr/bin/env python3
"""Build compact Wizardry VI glyph assets from an official Galmuri7 KBITX.

This decoder is adapted from the already validated Wizardry VII Galmuri7
pipeline.  KBITX glyph data is *not* plain hexadecimal text: the ``d`` field is
base64 (without required padding) containing ULEB128 dimensions and an RLE-like
pixel stream.

The repository does not vendor Galmuri7.  Pass a local/official
``Galmuri7.kbitx`` plus a W6 codebook JSON produced by ``korean_codec.py``.
Only glyphs actually used by the translation are emitted.

Output layout::

    glyph 0: 8 bytes
    glyph 1: 8 bytes
    ...

Rows 0..6 contain the 7x7 Galmuri bitmap in bits 7..1; row 7 is blank.  This is
convenient for W6's WFONT0-style 8x8 renderer while keeping the compact asset
at ``8 * codebook_glyph_count`` bytes.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
from korean_codec import Codebook  # noqa: E402

GLYPH_WIDTH = 7
GLYPH_HEIGHT = 7
OUTPUT_ROWS = 8


def decode_no_padding(value: str) -> bytes:
    value += "=" * ((4 - len(value) % 4) % 4)
    return base64.b64decode(value)


def read_uleb128(data: bytes, cursor: int) -> tuple[int, int]:
    value = 0
    shift = 0
    for _ in range(5):
        if cursor >= len(data):
            raise ValueError("truncated ULEB128 value")
        current = data[cursor]
        cursor += 1
        value |= (current & 0x7F) << shift
        if not current & 0x80:
            return value, cursor
        shift += 7
    raise ValueError("ULEB128 value is too long")


def decode_bitmap(encoded: str) -> list[list[int]]:
    """Decode one KBITX ``d`` payload to an 8-bit grayscale bitmap."""
    data = decode_no_padding(encoded)
    cursor = 0
    height, cursor = read_uleb128(data, cursor)
    width, cursor = read_uleb128(data, cursor)
    repeat_count = 0
    repeat_color: int | None = None
    bitmap: list[list[int]] = []

    for _ in range(height):
        row: list[int] = []
        for _ in range(width):
            if repeat_count <= 0:
                if cursor >= len(data):
                    raise ValueError("truncated KBITX run control")
                control = data[cursor]
                cursor += 1
                repeat_count = control & 0x1F
                if control & 0x20:
                    repeat_count <<= 5
                if repeat_count <= 0:
                    raise ValueError("invalid zero-length KBITX run")
                color_type = control & 0xC0
                if color_type == 0x00:
                    repeat_color = 0x00
                elif color_type == 0x40:
                    repeat_color = 0xFF
                elif color_type == 0x80:
                    if cursor >= len(data):
                        raise ValueError("truncated KBITX repeated color")
                    repeat_color = data[cursor]
                    cursor += 1
                else:
                    repeat_color = None
            repeat_count -= 1
            if repeat_color is None:
                if cursor >= len(data):
                    raise ValueError("truncated KBITX literal pixel")
                color = data[cursor]
                cursor += 1
            else:
                color = repeat_color
            row.append(color)
        bitmap.append(row)
    return bitmap


def to_7x7_rows(bitmap: list[list[int]]) -> bytes:
    """Convert a Galmuri monochrome bitmap to seven 1bpp row bytes."""
    if len(bitmap) > GLYPH_HEIGHT:
        raise ValueError(f"bitmap height {len(bitmap)} exceeds {GLYPH_HEIGHT}")
    if any(len(row) > GLYPH_WIDTH for row in bitmap):
        raise ValueError("bitmap width exceeds seven pixels")

    output = bytearray(GLYPH_HEIGHT)
    for y, source_row in enumerate(bitmap):
        row_value = 0
        for x, color in enumerate(source_row):
            if color >= 0x80:
                row_value |= 1 << (7 - x)
        output[y] = row_value
    return bytes(output)


def extract_codebook_rows(source: Path, codebook: Codebook) -> dict[str, bytes]:
    """Decode only the KBITX glyphs required by ``codebook``."""
    wanted = {ord(ch): ch for ch in codebook.characters}
    found: dict[str, bytes] = {}
    for _event, element in ET.iterparse(source, events=("end",)):
        if element.tag.rsplit("}", 1)[-1] != "g":
            continue
        codepoint_text = element.get("u")
        data_text = element.get("d")
        if codepoint_text is not None and data_text is not None:
            try:
                # Galmuri KBITX stores u as a decimal Unicode codepoint.
                codepoint = int(codepoint_text)
            except ValueError:
                codepoint = -1
            ch = wanted.get(codepoint)
            if ch is not None:
                found[ch] = to_7x7_rows(decode_bitmap(data_text))
        element.clear()

    missing = [ch for ch in codebook.characters if ch not in found]
    if missing:
        preview = ", ".join(f"{ch!r}/U+{ord(ch):04X}" for ch in missing[:12])
        raise ValueError(
            f"Galmuri7 source is missing {len(missing)} codebook glyphs (first: {preview})"
        )
    return found


def build_compact_table(rows_by_character: dict[str, bytes], codebook: Codebook) -> bytes:
    """Emit codebook-order 8x8 glyphs (7 Galmuri rows + blank baseline row)."""
    output = bytearray()
    for ch in codebook.characters:
        rows = rows_by_character[ch]
        if len(rows) != GLYPH_HEIGHT:
            raise ValueError(f"glyph {ch!r} has {len(rows)} rows; expected {GLYPH_HEIGHT}")
        output.extend(rows)
        output.append(0)
    return bytes(output)


def build_assets(source: Path, codebook: Codebook) -> tuple[bytes, dict[str, object]]:
    rows = extract_codebook_rows(source, codebook)
    table = build_compact_table(rows, codebook)
    metadata: dict[str, object] = {
        "source": source.name,
        "encoding": "w6-highbit-pair-v1",
        "glyph_count": len(codebook.characters),
        "glyph_width": GLYPH_WIDTH,
        "glyph_height": GLYPH_HEIGHT,
        "bytes_per_glyph": OUTPUT_ROWS,
        "table_bytes": len(table),
        "characters": [
            {
                "index": index,
                "character": ch,
                "codepoint": f"U+{ord(ch):04X}",
                "pair": f"{codebook.pair_for_index(index)[0]:02X} {codebook.pair_for_index(index)[1]:02X}",
            }
            for index, ch in enumerate(codebook.characters)
        ],
    }
    return table, metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="local Galmuri7.kbitx")
    parser.add_argument("--codebook", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="compact raw 8-byte glyph table")
    parser.add_argument("--metadata", type=Path, required=True)
    args = parser.parse_args()

    codebook = Codebook.load(args.codebook)
    table, metadata = build_assets(args.input, codebook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(table)
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({k: v for k, v in metadata.items() if k != "characters"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
