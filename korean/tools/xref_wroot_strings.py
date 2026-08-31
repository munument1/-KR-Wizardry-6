#!/usr/bin/env python3
"""Static xref audit for user-visible ASCII in Wizardry VI WROOT.EXE.

The DOS MZ image keeps most normal strings in DGROUP, while several fatal
startup errors live inline in the code segment.  This tool finds referenced
printable strings without requiring Capstone/Ghidra and emits evidence that
can be reviewed before a string is promoted to the localization inventory.

It does not modify the game and does not ship any original game data.
"""

from __future__ import annotations

import argparse
import csv
import re
import struct
from dataclasses import dataclass
from pathlib import Path

PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{4,}")
REGISTER_IMM16 = {
    0xB8: "AX",
    0xB9: "CX",
    0xBA: "DX",
    0xBB: "BX",
    0xBC: "SP",
    0xBD: "BP",
    0xBE: "SI",
    0xBF: "DI",
}

# Known non-localizable technical names.  Keeping this explicit makes the
# report conservative: referenced filenames are evidence that the xref logic
# works, but they are not translation targets.
TECHNICAL_PATTERNS = (
    re.compile(r"^[A-Z0-9_]+\.(?:OVR|DBS|HDR|PIC|EGA|CGA|T16|SND)$", re.I),
    re.compile(r"^[A-Z0-9_]+$", re.I),
    re.compile(r"^\.ovr$", re.I),
)


@dataclass(frozen=True)
class MZInfo:
    header_bytes: int
    entry_cs: int
    entry_ip: int
    relocation_count: int
    relocation_table_offset: int
    dgroup_segment: int
    dgroup_file_base: int


def parse_mz(data: bytes) -> MZInfo:
    if len(data) < 0x1C or data[:2] != b"MZ":
        raise ValueError("not an MZ executable")

    (
        _magic,
        _cblp,
        _cp,
        crlc,
        cparhdr,
        _minalloc,
        _maxalloc,
        _ss,
        _sp,
        _csum,
        ip,
        cs,
        lfarlc,
        _ovno,
    ) = struct.unpack_from("<14H", data, 0)

    header_bytes = cparhdr * 16
    if crlc < 1:
        raise ValueError("WROOT.EXE has no relocation entry; cannot derive DGROUP")

    # WROOT's sole relocation is the immediate word of the startup
    # `mov bp, <DGROUP paragraph>` instruction.  The on-disk pre-relocation
    # word is therefore the DGROUP segment relative to the load module.
    reloc_off, reloc_seg = struct.unpack_from("<HH", data, lfarlc)
    reloc_file = header_bytes + reloc_seg * 16 + reloc_off
    if reloc_file + 2 > len(data):
        raise ValueError("relocation target outside file")
    dgroup_segment = struct.unpack_from("<H", data, reloc_file)[0]
    dgroup_file_base = header_bytes + dgroup_segment * 16
    if not (header_bytes <= dgroup_file_base < len(data)):
        raise ValueError("derived DGROUP base outside file")

    return MZInfo(
        header_bytes=header_bytes,
        entry_cs=cs,
        entry_ip=ip,
        relocation_count=crlc,
        relocation_table_offset=lfarlc,
        dgroup_segment=dgroup_segment,
        dgroup_file_base=dgroup_file_base,
    )


def is_technical(text: str) -> bool:
    return any(p.fullmatch(text) for p in TECHNICAL_PATTERNS)


def find_mov_imm16_refs(data: bytes, end: int, value: int) -> list[tuple[int, str]]:
    target = struct.pack("<H", value & 0xFFFF)
    refs: list[tuple[int, str]] = []
    for opcode, reg in REGISTER_IMM16.items():
        pattern = bytes([opcode]) + target
        start = 0
        while True:
            hit = data.find(pattern, start, end)
            if hit < 0:
                break
            refs.append((hit, f"MOV {reg},0x{value & 0xFFFF:04X}"))
            start = hit + 1
    return sorted(set(refs))


def find_cs_dos_refs(
    data: bytes,
    code_end: int,
    cs_string_offset: int,
    prefix_search: int = 6,
) -> list[tuple[int, str, int]]:
    """Find `mov dx,imm16` references to a CS-inline DOS `$` string.

    Fatal strings in WROOT often start with CR/LF/BEL bytes before the first
    printable character, so search a few bytes before the printable run.
    """
    refs: list[tuple[int, str, int]] = []
    for delta in range(-prefix_search, 1):
        value = (cs_string_offset + delta) & 0xFFFF
        pattern = b"\xBA" + struct.pack("<H", value)
        start = 0
        while True:
            hit = data.find(pattern, start, code_end)
            if hit < 0:
                break
            refs.append((hit, f"MOV DX,0x{value:04X}", delta))
            start = hit + 1
    return sorted(set(refs))


def audit(data: bytes) -> tuple[MZInfo, list[dict[str, str]]]:
    mz = parse_mz(data)
    rows: list[dict[str, str]] = []

    for match in PRINTABLE_RE.finditer(data):
        raw = match.group()
        if len(raw) > 160:
            continue
        text = raw.decode("ascii", errors="strict")
        if sum(ch.isalpha() for ch in text) < 3:
            continue

        file_offset = match.start()
        refs_text: list[str] = []

        if file_offset >= mz.dgroup_file_base:
            storage = "DGROUP"
            logical_offset = file_offset - mz.dgroup_file_base
            refs = find_mov_imm16_refs(data, mz.dgroup_file_base, logical_offset)
            refs_text = [f"0x{off:05X}:{ins}" for off, ins in refs]
        else:
            storage = "CS_INLINE"
            logical_offset = file_offset - mz.header_bytes - mz.entry_cs * 16
            refs = find_cs_dos_refs(data, mz.dgroup_file_base, logical_offset)
            refs_text = [
                f"0x{off:05X}:{ins}:printable_delta={delta:+d}"
                for off, ins, delta in refs
            ]

        if not refs_text:
            continue

        technical = is_technical(text)
        classification = "REFERENCED_TECHNICAL" if technical else "REFERENCED_TEXT_CANDIDATE"
        rows.append(
            {
                "file_offset_hex": f"0x{file_offset:05X}",
                "storage": storage,
                "logical_offset_hex": f"0x{logical_offset & 0xFFFF:04X}",
                "byte_length": str(len(raw)),
                "source_text": text,
                "xref_count": str(len(refs_text)),
                "xrefs": " | ".join(refs_text),
                "classification": classification,
            }
        )

    return mz, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wroot", type=Path, help="path to original WROOT.EXE")
    parser.add_argument("--output", type=Path, help="optional CSV output")
    args = parser.parse_args()

    data = args.wroot.read_bytes()
    mz, rows = audit(data)

    print(f"MZ header bytes: 0x{mz.header_bytes:X}")
    print(f"DGROUP segment: 0x{mz.dgroup_segment:04X}")
    print(f"DGROUP file base: 0x{mz.dgroup_file_base:05X}")
    print(f"Referenced printable strings: {len(rows)}")
    print(
        "Localization candidates: "
        + str(sum(r["classification"] == "REFERENCED_TEXT_CANDIDATE" for r in rows))
    )

    for row in rows:
        print(
            f'{row["file_offset_hex"]} {row["classification"]:<25} '
            f'{row["source_text"]!r} -> {row["xrefs"]}'
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "file_offset_hex",
            "storage",
            "logical_offset_hex",
            "byte_length",
            "source_text",
            "xref_count",
            "xrefs",
            "classification",
        ]
        with args.output.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {args.output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
