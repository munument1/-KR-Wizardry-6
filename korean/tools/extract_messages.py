#!/usr/bin/env python3
"""Lossless Wizardry VI MSG.DBS extractor and structural validator.

This tool intentionally extracts *individual message IDs*, rather than the
joined range strings used by the interactive viewer.  It preserves every
byte needed for later reinsertion: range metadata, record pointers, decoded
length, an escaped text representation, and the decoded bytes as hex.

Usage:
    python korean/tools/extract_messages.py --gamedata gamedata --csv out.csv
    python korean/tools/extract_messages.py --gamedata gamedata --validate-only
"""
from __future__ import annotations

import argparse
import csv
import re
import struct
from dataclasses import dataclass
from pathlib import Path

BANK_SIZE = 1024


def resolve_data_file(gamedata: Path, canonical_name: str) -> Path:
    """Resolve a game-data filename case-insensitively.

    Retail archives and user installs vary between upper- and lower-case names,
    especially when copied between DOS/Windows and Unix-like filesystems.
    """
    direct = gamedata / canonical_name
    if direct.exists():
        return direct
    wanted = canonical_name.casefold()
    for child in gamedata.iterdir():
        if child.is_file() and child.name.casefold() == wanted:
            return child
    raise FileNotFoundError(f"Required game data file not found: {canonical_name}")


@dataclass(frozen=True)
class MessageRange:
    range_index: int
    start_id: int
    bank: int
    bank_offset: int
    id_span: int


class HuffmanDecoder:
    """Wizardry VI Huffman tree decoder (MISC.HDR, MSB-first bitstream)."""

    def __init__(self, tree_data: bytes):
        self.nodes: list[tuple[int, int]] = []
        for i in range(0, len(tree_data) - 3, 4):
            self.nodes.append(struct.unpack_from("<hh", tree_data, i))

    @classmethod
    def from_file(cls, path: Path) -> "HuffmanDecoder":
        return cls(path.read_bytes())

    def decode(self, compressed_data: bytes, uncompressed_len: int) -> bytes:
        out = bytearray()
        node_idx = 0
        bit_ptr = 0
        while len(out) < uncompressed_len:
            byte_idx = bit_ptr // 8
            if byte_idx >= len(compressed_data):
                raise ValueError(
                    f"Huffman bitstream ended after {len(out)}/{uncompressed_len} bytes"
                )
            bit_idx = bit_ptr % 8
            bit = (compressed_data[byte_idx] >> (7 - bit_idx)) & 1
            bit_ptr += 1
            if not (0 <= node_idx < len(self.nodes)):
                raise ValueError(f"Invalid Huffman node index {node_idx}")
            left, right = self.nodes[node_idx]
            next_val = left if bit == 0 else right
            if next_val >= 0:
                out.append(next_val & 0xFF)
                node_idx = 0
            else:
                node_idx = -next_val
        return bytes(out)


def parse_header(path: Path) -> list[MessageRange]:
    data = path.read_bytes()
    if len(data) < 2 or len(data) % 2:
        raise ValueError(f"Invalid MSG.HDR size: {len(data)}")
    words = list(struct.unpack(f"<{len(data)//2}H", data))
    count = words[0]
    expected_words = 1 + count * 3
    if len(words) < expected_words:
        raise ValueError(
            f"MSG.HDR declares {count} ranges but only {len(words)} words are present"
        )
    ranges: list[MessageRange] = []
    p = 1
    for range_index in range(count):
        start_id, start_offset, packed = words[p : p + 3]
        p += 3
        ranges.append(
            MessageRange(
                range_index=range_index,
                start_id=start_id,
                bank=(packed >> 8) & 0xFF,
                bank_offset=start_offset,
                id_span=packed & 0xFF,
            )
        )
    return ranges


def escape_bytes(data: bytes) -> str:
    """Reversible spreadsheet-safe representation preserving whitespace.

    Printable ASCII is emitted literally.  Backslash is escaped as ``\\\\``
    so literal text cannot collide with control escapes.  Non-printable bytes
    use ``<0xNN>``; this matches the existing localization sheet convention.
    """
    out: list[str] = []
    for b in data:
        if b == 0x5C:  # backslash
            out.append("\\\\")
        elif 0x20 <= b <= 0x7E:
            out.append(chr(b))
        else:
            out.append(f"<0x{b:02X}>")
    return "".join(out)


_ESCAPE_RE = re.compile(r"<0x([0-9A-Fa-f]{2})>")


def unescape_text(text: str) -> bytes:
    """Inverse of :func:`escape_bytes`."""
    out = bytearray()
    i = 0
    while i < len(text):
        if text.startswith("\\\\", i):
            out.append(0x5C)
            i += 2
            continue
        m = _ESCAPE_RE.match(text, i)
        if m:
            out.append(int(m.group(1), 16))
            i = m.end()
            continue
        ch = text[i]
        code = ord(ch)
        if code > 0x7F:
            raise ValueError(f"Non-ASCII literal in escaped source text: {ch!r}")
        out.append(code)
        i += 1
    return bytes(out)


def readable_preview(data: bytes) -> str:
    """Human-oriented preview only; never use this column for reinsertion."""
    out: list[str] = []
    for b in data:
        ch = chr(b)
        if b == 0x1F or ch in "!%":
            out.append("\n\n")
        elif ch == "$":
            out.append("\n")
        elif b in (0x1E, 0x0E):
            out.append(" ")
        elif b < 0x20:
            out.append(f"<0x{b:02X}>")
        else:
            out.append(ch)
    text = "".join(out)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract(gamedata: Path) -> tuple[list[dict[str, object]], dict[str, int]]:
    ranges = parse_header(resolve_data_file(gamedata, "MSG.HDR"))
    dbs = resolve_data_file(gamedata, "MSG.DBS").read_bytes()
    decoder = HuffmanDecoder.from_file(resolve_data_file(gamedata, "MISC.HDR"))
    if len(dbs) % BANK_SIZE:
        raise ValueError(f"MSG.DBS size {len(dbs)} is not a multiple of {BANK_SIZE}")

    rows: list[dict[str, object]] = []
    seen_ids: set[int] = set()
    used_record_ptrs: set[int] = set()
    duplicate_ids = 0
    duplicate_ptrs = 0

    for entry in ranges:
        pos = entry.bank * BANK_SIZE + entry.bank_offset
        for delta in range(entry.id_span + 1):
            message_id = entry.start_id + delta
            if message_id in seen_ids:
                duplicate_ids += 1
            seen_ids.add(message_id)
            if pos in used_record_ptrs:
                duplicate_ptrs += 1
            used_record_ptrs.add(pos)

            if not (0 <= pos < len(dbs)):
                raise ValueError(
                    f"Message {message_id}: record pointer 0x{pos:X} outside MSG.DBS"
                )
            record_length = dbs[pos]
            record_end = pos + 1 + record_length
            if record_end > len(dbs):
                raise ValueError(
                    f"Message {message_id}: record at 0x{pos:X} overruns MSG.DBS"
                )
            payload = dbs[pos + 1 : record_end]
            decoded_length = payload[0] if payload else 0
            decoded = decoder.decode(payload[1:], decoded_length) if payload else b""
            escaped = escape_bytes(decoded)
            if unescape_text(escaped) != decoded:
                raise AssertionError(f"Message {message_id}: source_text round-trip failed")

            rows.append(
                {
                    "message_id": message_id,
                    "range_index": entry.range_index,
                    "range_start_id": entry.start_id,
                    "bank": entry.bank,
                    "bank_offset": pos - entry.bank * BANK_SIZE,
                    "absolute_offset": pos,
                    "record_length": record_length,
                    "decoded_length": decoded_length,
                    "source_text": escaped,
                    "source_bytes_hex": decoded.hex().upper(),
                    "readable_preview": readable_preview(decoded),
                }
            )
            pos = record_end

    summary = {
        "range_count": len(ranges),
        "message_count": len(rows),
        "unique_message_ids": len(seen_ids),
        "duplicate_message_ids": duplicate_ids,
        "duplicate_record_ptrs": duplicate_ptrs,
        "bank_count": len(dbs) // BANK_SIZE,
    }
    return rows, summary


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    fields = [
        "message_id",
        "range_index",
        "range_start_id",
        "bank",
        "bank_offset",
        "absolute_offset",
        "record_length",
        "decoded_length",
        "source_text",
        "source_bytes_hex",
        "readable_preview",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gamedata", type=Path, default=Path("gamedata"))
    ap.add_argument("--csv", type=Path)
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    rows, summary = extract(args.gamedata)
    for key, value in summary.items():
        print(f"{key}: {value}")
    if summary["duplicate_message_ids"] or summary["duplicate_record_ptrs"]:
        raise SystemExit("Structural validation failed: duplicate ID/pointer detected")
    if not args.validate_only:
        out = args.csv or Path("korean/generated/w6_messages_lossless.csv")
        write_csv(rows, out)
        print(f"wrote: {out}")


if __name__ == "__main__":
    main()
