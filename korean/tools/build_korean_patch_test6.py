#!/usr/bin/env python3
"""Runtime Test6: keep Test5 crash fix and cap compact character info to two Korean glyphs."""
from __future__ import annotations

import build_korean_patch as stable
import build_korean_patch_release as release


_test5_make_wbase = stable.make_wbase


def _make_wbase_compact_two_glyphs(original: bytes) -> tuple[bytes, dict[str, object]]:
    """Keep gender as a string, but cap compact race/class fields at 4 bytes.

    Korean custom glyphs use two bytes each, so four bytes are exactly two
    visible Korean glyphs.  This mirrors the compact party-panel presentation
    without splitting a lead/trail pair or letting a long string spill into the
    adjacent character-info columns.
    """
    built, report = _test5_make_wbase(original)
    patched = bytearray(built)

    for offset, label in (
        (0x1FF3, "roster race compact limit mode 1"),
        (0x2034, "roster class compact limit mode 1"),
        (0x20DC, "roster race compact limit mode 2"),
        (0x2112, "roster class compact limit mode 2"),
    ):
        actual = bytes(patched[offset : offset + 4])
        if actual != b"\x90\x90\x90\x90":
            raise ValueError(f"{label}: expected Test5 unlimited-string patch, got {actual.hex(' ')}")
        # Retail wrote NUL to BP-11h, i.e. after 3 bytes. Move that terminator
        # one byte later to BP-10h so the Korean two-byte encoding ends on a
        # complete pair boundary: 4 bytes == two glyphs.
        patched[offset : offset + 4] = bytes.fromhex("C6 46 F0 00")

    report = dict(report)
    report["race_class_compact_bytes"] = 4
    report["race_class_compact_korean_glyphs"] = 2
    report["gender_compact_korean_glyphs"] = 2
    return bytes(patched), report


stable.make_wbase = _make_wbase_compact_two_glyphs


if __name__ == "__main__":
    raise SystemExit(release.main())
