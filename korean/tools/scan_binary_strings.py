#!/usr/bin/env python3
"""Audit plain ASCII strings in Wizardry VI DOS EXE/OVR binaries.

The output is an *audit*, not a translation list: printable runs in 16-bit x86
code create many false positives.  The classifier deliberately promotes only
strong user-visible candidates and labels obvious filenames/internal symbols.
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

PRINTABLE = set(range(0x20, 0x7F))
FILE_RE = re.compile(
    r"^(?:[A-Z0-9_^%.-]+\.(?:OVR|PIC|EGA|CGA|T16|SND|DBS|HDR|DRV|BAT|COM)|WPORT\d+\.[A-Z0-9]+)$",
    re.I,
)
USER_PATTERNS = [
    re.compile(p, re.I)
    for p in (
        r"unable to ",
        r"i/o error",
        r"invalid font",
        r"insert (?:savegame )?disk",
        r"into drive",
        r"press ",
        r"error .*loading overlay",
        r"is required",
        r"too many args",
    )
]


def iter_ascii_runs(data: bytes, min_len: int = 4):
    start = None
    for i, b in enumerate(data):
        if b in PRINTABLE:
            if start is None:
                start = i
        elif start is not None:
            if i - start >= min_len:
                yield start, data[start:i].decode("ascii")
            start = None
    if start is not None and len(data) - start >= min_len:
        yield start, data[start:].decode("ascii")


def classify(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if FILE_RE.fullmatch(stripped):
        return "INTERNAL_REFERENCE", "filename/resource/overlay reference"
    if any(p.search(stripped) for p in USER_PATTERNS):
        return "LIKELY_USER_VISIBLE", "runtime error or DOS prompt wording"
    # Plain English words are still unsafe in x86 binaries unless context is known.
    alpha = sum(ch.isalpha() for ch in stripped)
    spaces = stripped.count(" ")
    if len(stripped) >= 8 and alpha / max(1, len(stripped)) >= 0.70 and spaces >= 1:
        return "REVIEW", "human-like ASCII; requires code/reference tracing"
    return "LOW_CONFIDENCE", "likely executable bytes or compact internal data"


def scan_file(path: Path, min_len: int) -> list[dict[str, object]]:
    data = path.read_bytes()
    out = []
    for offset, text in iter_ascii_runs(data, min_len=min_len):
        status, reason = classify(text)
        out.append(
            {
                "file_name": path.name.upper(),
                "offset_hex": f"0x{offset:05X}",
                "offset_decimal": offset,
                "byte_length": len(text),
                "source_text": text,
                "classification": status,
                "reason": reason,
            }
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gamedata", type=Path, default=Path("gamedata"))
    ap.add_argument("--csv", type=Path, required=True)
    ap.add_argument("--min-length", type=int, default=4)
    ap.add_argument("--candidates-only", action="store_true")
    args = ap.parse_args()

    candidates = [
        p for p in args.gamedata.iterdir()
        if p.is_file() and (
            p.name.casefold() == "wroot.exe"
            or (p.name.casefold().startswith("w") and p.suffix.casefold() == ".ovr")
        )
    ]
    candidates.sort(key=lambda p: (p.name.casefold() != "wroot.exe", p.name.casefold()))
    rows: list[dict[str, object]] = []
    for path in candidates:
        rows.extend(scan_file(path, args.min_length))
    if args.candidates_only:
        rows = [r for r in rows if r["classification"] in {"LIKELY_USER_VISIBLE", "REVIEW"}]

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "file_name", "offset_hex", "offset_decimal", "byte_length",
        "source_text", "classification", "reason",
    ]
    with args.csv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    from collections import Counter
    counts = Counter(str(r["classification"]) for r in rows)
    print(f"rows: {len(rows)}")
    for k, v in sorted(counts.items()):
        print(f"{k}: {v}")
    print(f"wrote: {args.csv}")


if __name__ == "__main__":
    main()
