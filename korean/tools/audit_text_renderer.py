#!/usr/bin/env python3
"""Audit known Wizardry VI DOS text-renderer and MSG-page-loader signatures.

This tool does not modify WROOT.EXE or EGA.DRV. WROOT offsets below are file
offsets; subtract the 0x200 MZ header for load-module CS offsets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED_WROOT_SHA256 = "6ae1642e31e0b0a7965271dada8cb1eec82626bb907600d208dbeb728f26eba0"
EXPECTED_WROOT_SIZE = 67134
EXPECTED_MZ_HEADER = 0x200


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mz_header_size(data: bytes) -> int:
    if len(data) < 0x1C or data[:2] != b"MZ":
        raise ValueError("WROOT is not an MZ executable")
    return struct.unpack_from("<H", data, 0x08)[0] * 16


def expect(data: bytes, offset: int, signature: bytes, label: str, issues: list[str]) -> bool:
    actual = data[offset : offset + len(signature)]
    if actual != signature:
        issues.append(
            f"{label}: expected {signature.hex(' ').upper()} at 0x{offset:X}, "
            f"found {actual.hex(' ').upper()}"
        )
        return False
    return True


def longest_zero_run(data: bytes, start: int = 0) -> tuple[int, int]:
    best_start = best_end = start
    run_start: int | None = None
    for pos in range(start, len(data)):
        if data[pos] == 0:
            if run_start is None:
                run_start = pos
        elif run_start is not None:
            if pos - run_start > best_end - best_start:
                best_start, best_end = run_start, pos
            run_start = None
    if run_start is not None and len(data) - run_start > best_end - best_start:
        best_start, best_end = run_start, len(data)
    return best_start, best_end


def audit(wroot: bytes, ega: bytes) -> dict[str, object]:
    issues: list[str] = []
    header = mz_header_size(wroot)
    if len(wroot) != EXPECTED_WROOT_SIZE:
        issues.append(f"WROOT size is {len(wroot)}; expected {EXPECTED_WROOT_SIZE}")
    if header != EXPECTED_MZ_HEADER:
        issues.append(f"MZ header size is 0x{header:X}; expected 0x{EXPECTED_MZ_HEADER:X}")

    signatures = [
        (0x24B7, bytes.fromhex("55 8B EC 83 EC 06 1E 06 57 56"), "WROOT draw-char file:24B7 / CS:22B7"),
        (0x26E9, bytes.fromhex("55 8B EC 83 EC 04 56 06 1E"), "WROOT WFONT0 string file:26E9 / CS:24E9"),
        (0x26FB, bytes.fromhex("8B 5E FE FF 46 FE 8A 07 32 E4 0A C0"), "WROOT WFONT0 one-byte iteration file:26FB / CS:24FB"),
        (0x270E, bytes.fromhex("E8 A6 FD"), "WROOT WFONT0 draw-char call file:270E / CS:250E"),
        (0x271D, bytes.fromhex("55 8B EC 83 EC 04 56 06 1E"), "WROOT WFONT1-4 string file:271D / CS:251D"),
        (0x2734, bytes.fromhex("8B 5E FE FF 46 FE 8A 07 32 E4 0A C0"), "WROOT WFONT1-4 one-byte iteration file:2734 / CS:2534"),
        (0x2747, bytes.fromhex("E8 99 FE"), "WROOT WFONT1-4 draw-char call file:2747 / CS:2547"),
        (0x25B0, bytes.fromhex("2E FF 1E 8A 1B"), "WROOT driver entry0 call file:25B0 / CS:23B0"),
        (0x2E69, bytes.fromhex("2E FF 1E 8A 1B"), "WROOT refresh entry0 call file:2E69 / CS:2C69"),
        (0x2E5C, bytes.fromhex("2E FF 1E 8E 1B"), "WROOT refresh entry1 call file:2E5C / CS:2C5C"),
        (0x08AA, bytes.fromhex("55 8B EC 56 BE 00 00"), "WROOT MSG page loader file:08AA / CS:06AA"),
        (0x08F1, bytes.fromhex("8B 46 04 99 B9 0A 00 D1 E0 D1 D2 E2 FA 52 50 FF 36 44 08"), "WROOT MSG page<<10 seek file:08F1 / CS:06F1"),
        (0x090A, bytes.fromhex("B8 00 04 50 B8 3E 1C 50 FF 36 44 08"), "WROOT MSG 0x400-byte read file:090A / CS:070A"),
    ]
    for offset, sig, label in signatures:
        expect(wroot, offset, sig, label, issues)

    ega_signatures = [
        (0x000, bytes.fromhex("E9 00 00"), "EGA COM jump to entry table"),
        (0x003, bytes.fromhex("E8 94 01 CB"), "EGA entry0 COM:0103 -> 029A"),
        (0x007, bytes.fromhex("E8 30 04 CB"), "EGA entry1 COM:0107 -> 053A"),
        (0x1A7, bytes.fromhex("8A D8 32 FF B1 03 D3 E3"), "EGA WFONT0 AL*8 COM:02A7"),
        (0x444, bytes.fromhex("8A D8 32 FF B1 05 D3 E3"), "EGA WFONT1-4 AL*32 COM:0544"),
        (0x1AF, bytes.fromhex("2E 8B 16 55 01"), "EGA WFONT0 segment pointer CS:0155"),
        (0x44E, bytes.fromhex("2E 8B 16 59 01"), "EGA WFONT1 segment pointer CS:0159"),
    ]
    for offset, sig, label in ega_signatures:
        expect(ega, offset, sig, label, issues)

    cave_start, cave_end = longest_zero_run(wroot, header)
    cave = {
        "file_start": cave_start,
        "file_end_exclusive": cave_end,
        "bytes": cave_end - cave_start,
        "cs_start": cave_start - header,
        "cs_end_exclusive": cave_end - header,
    }
    if cave_start != 0x4772 or cave_end != 0xFF82:
        issues.append(
            f"largest WROOT zero cave is 0x{cave_start:X}..0x{cave_end:X}; "
            "audited retail build expects 0x4772..0xFF82"
        )

    return {
        "passed": not issues,
        "issues": issues,
        "wroot_size": len(wroot),
        "wroot_sha256": sha256(wroot),
        "expected_wroot_sha256": EXPECTED_WROOT_SHA256,
        "wroot_sha_matches": sha256(wroot) == EXPECTED_WROOT_SHA256,
        "mz_header_bytes": header,
        "ega_size": len(ega),
        "ega_sha256": sha256(ega),
        "resident_zero_cave": cave,
        "msg_page_loader": {
            "file_offset": "0x08AA",
            "cs_offset": "0x06AA",
            "page_seek_rule": "page << 10",
            "read_bytes": 1024,
            "cache_entries": 4,
            "hardcoded_80_bank_limit_observed": False,
        },
        "hook_points": {
            "draw_character_file": "0x24B7",
            "draw_character_cs": "0x22B7",
            "string_wfont0_file": "0x26E9",
            "string_wfont0_cs": "0x24E9",
            "string_wfont1_4_file": "0x271D",
            "string_wfont1_4_cs": "0x251D",
            "driver_entry0_call_file": "0x25B0",
            "driver_entry0_call_cs": "0x23B0",
            "refresh_driver_entry0_call_file": "0x2E69",
            "refresh_driver_entry0_call_cs": "0x2C69",
            "refresh_driver_entry1_call_file": "0x2E5C",
            "refresh_driver_entry1_call_cs": "0x2C5C",
            "ega_entry0_com": "0x0103",
            "ega_entry1_com": "0x0107",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wroot", type=Path, required=True)
    parser.add_argument("--ega", type=Path, required=True)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = audit(args.wroot.read_bytes(), args.ega.read_bytes())
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(text, encoding="utf-8", newline="\n")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
