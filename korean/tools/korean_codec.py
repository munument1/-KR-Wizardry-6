#!/usr/bin/env python3
"""Wizardry VI compact two-byte custom-glyph codebook codec.

The audited retail W6 message corpus uses only bytes below 0x80.  The Korean
build therefore reserves every high-bit byte (0x80..0xFF) for a two-byte custom
character.  The codebook contains only non-ASCII characters actually used by
translated text instead of allocating all Unicode/Hangul glyphs up front.

Pair layout for codebook index N::

    lead  = 0x80 + (N // 128)
    trail = 0x80 + (N % 128)

Every custom character is exactly two decoded MSG bytes.  The current renderer
design budgets 11 index bits (2,048 glyphs).  That is a runtime/layout limit,
not an encoding limit: the pair namespace itself has 16,384 entries.  If the
final translation exceeds 2,048 distinct non-ASCII glyphs, the renderer must be
expanded deliberately instead of silently changing the on-disk encoding.

Spreadsheet control notation such as ``<0x15>`` is parsed as one literal byte.
Literal bytes >=0x80 are rejected because they collide with the custom-pair
namespace.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LEAD_BASE = 0x80
TRAIL_BASE = 0x80
RADIX = 128
MAX_PAIR_GLYPHS = 128 * 128
MAX_RUNTIME_GLYPHS = 2048
_CONTROL_ESCAPE = re.compile(r"<0x([0-9A-Fa-f]{2})>")


def iter_translation_units(text: str) -> list[int | str]:
    """Split spreadsheet display notation into literal byte tokens/chars."""
    units: list[int | str] = []
    pos = 0
    while pos < len(text):
        match = _CONTROL_ESCAPE.match(text, pos)
        if match:
            units.append(int(match.group(1), 16))
            pos = match.end()
            continue
        units.append(text[pos])
        pos += 1
    return units


def _validate_custom_character(ch: str) -> None:
    if len(ch) != 1:
        raise ValueError("codebook entries must be single Unicode characters")
    cp = ord(ch)
    if cp <= 0x7F:
        raise ValueError(f"ASCII character {ch!r} does not belong in the custom codebook")
    # Runtime storage is an index, so it does not care whether the glyph is
    # Hangul, punctuation, or another symbol.  The Galmuri/KBITX builder is the
    # authority for whether a drawable glyph actually exists.


@dataclass(frozen=True)
class Codebook:
    characters: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.characters) > MAX_RUNTIME_GLYPHS:
            raise ValueError(
                f"codebook has {len(self.characters)} glyphs; current runtime limit is "
                f"{MAX_RUNTIME_GLYPHS}"
            )
        if len(set(self.characters)) != len(self.characters):
            raise ValueError("codebook contains duplicate characters")
        for ch in self.characters:
            _validate_custom_character(ch)

    @property
    def index_by_character(self) -> dict[str, int]:
        return {ch: index for index, ch in enumerate(self.characters)}

    def pair_for_index(self, index: int) -> tuple[int, int]:
        if not 0 <= index < len(self.characters):
            raise ValueError(f"codebook index out of range: {index}")
        if index >= MAX_PAIR_GLYPHS:
            raise ValueError(f"codebook index exceeds two-byte namespace: {index}")
        return LEAD_BASE + index // RADIX, TRAIL_BASE + index % RADIX

    def pair_for_character(self, ch: str) -> tuple[int, int]:
        try:
            index = self.index_by_character[ch]
        except KeyError as exc:
            raise ValueError(f"character {ch!r} is absent from the codebook") from exc
        return self.pair_for_index(index)

    def index_for_pair(self, lead: int, trail: int) -> int:
        if not LEAD_BASE <= lead <= 0xFF or not TRAIL_BASE <= trail <= 0xFF:
            raise ValueError(f"invalid custom pair {lead:02X} {trail:02X}")
        index = (lead - LEAD_BASE) * RADIX + (trail - TRAIL_BASE)
        if index >= len(self.characters):
            raise ValueError(f"custom pair points outside codebook: {lead:02X} {trail:02X}")
        return index

    def character_for_pair(self, lead: int, trail: int) -> str:
        return self.characters[self.index_for_pair(lead, trail)]

    def to_json_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "encoding": "w6-highbit-pair-v1",
            "lead_base": LEAD_BASE,
            "trail_base": TRAIL_BASE,
            "radix": RADIX,
            "runtime_glyph_limit": MAX_RUNTIME_GLYPHS,
            "characters": list(self.characters),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, object]) -> "Codebook":
        if data.get("encoding") != "w6-highbit-pair-v1":
            raise ValueError("unsupported W6 codebook encoding")
        chars = data.get("characters")
        if not isinstance(chars, list) or not all(isinstance(ch, str) for ch in chars):
            raise ValueError("codebook characters must be a JSON string array")
        return cls(tuple(chars))

    @classmethod
    def load(cls, path: Path) -> "Codebook":
        return cls.from_json_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
            newline="\n",
        )


def build_codebook(texts: Iterable[str]) -> Codebook:
    """Build a deterministic dense codebook from translated text.

    Custom characters are ordered by descending frequency and then Unicode
    codepoint.  Frequency ordering is not required for the fixed two-byte
    stream, but it keeps common glyphs at low indices and makes builds stable.
    """
    frequencies: Counter[str] = Counter()
    for text in texts:
        for unit in iter_translation_units(text):
            if isinstance(unit, int):
                if unit >= 0x80:
                    raise ValueError(
                        f"literal high-byte token <0x{unit:02X}> collides with custom pairs"
                    )
                continue
            if ord(unit) <= 0x7F:
                continue
            _validate_custom_character(unit)
            frequencies[unit] += 1
    ordered = tuple(sorted(frequencies, key=lambda ch: (-frequencies[ch], ord(ch))))
    return Codebook(ordered)


def encode_text(text: str, codebook: Codebook) -> bytes:
    """Encode one spreadsheet translation into the W6 decoded-byte stream."""
    out = bytearray()
    for unit in iter_translation_units(text):
        if isinstance(unit, int):
            if unit >= 0x80:
                raise ValueError(
                    f"literal high-byte token <0x{unit:02X}> collides with custom pairs"
                )
            out.append(unit)
            continue
        cp = ord(unit)
        if cp <= 0x7F:
            out.append(cp)
        else:
            out.extend(codebook.pair_for_character(unit))
    if len(out) > 0xFF:
        raise ValueError(f"encoded translation is {len(out)} bytes; MSG fragment maximum is 255")
    return bytes(out)


def decode_bytes(data: bytes, codebook: Codebook, *, escape_controls: bool = False) -> str:
    """Decode the custom stream; mainly used by tests/verification tools."""
    out: list[str] = []
    pos = 0
    while pos < len(data):
        value = data[pos]
        if value < 0x80:
            if escape_controls and (value < 0x20 or value == 0x7F):
                out.append(f"<0x{value:02X}>")
            else:
                out.append(chr(value))
            pos += 1
            continue
        if pos + 1 >= len(data):
            raise ValueError(f"truncated custom lead byte at offset {pos}: 0x{value:02X}")
        out.append(codebook.character_for_pair(value, data[pos + 1]))
        pos += 2
    return "".join(out)


def glyph_count(data: bytes, codebook: Codebook) -> int:
    """Count logical display glyphs in one encoded translation."""
    count = 0
    pos = 0
    while pos < len(data):
        value = data[pos]
        if value < 0x80:
            pos += 1
        else:
            if pos + 1 >= len(data):
                raise ValueError(f"truncated custom pair at offset {pos}")
            codebook.index_for_pair(value, data[pos + 1])
            pos += 2
        count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codebook", type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--encode")
    group.add_argument("--decode-hex")
    args = parser.parse_args()
    codebook = Codebook.load(args.codebook)
    if args.encode is not None:
        raw = encode_text(args.encode, codebook)
        print(raw.hex(" ").upper())
        print(f"bytes={len(raw)} glyphs={glyph_count(raw, codebook)}")
    else:
        raw = bytes.fromhex(args.decode_hex)
        print(decode_bytes(raw, codebook, escape_controls=True))
        print(f"bytes={len(raw)} glyphs={glyph_count(raw, codebook)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
