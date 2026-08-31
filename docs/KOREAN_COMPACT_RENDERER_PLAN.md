# Wizardry VI DOS compact Korean renderer plan

Date: 2026-08-31  
Branch: `korean-localization`

## Purpose

This document fixes the data contract between translated CSV text and the future
Wizardry VI DOS renderer.  The executable patch is intentionally not considered
finished yet.  The goal of this stage is to make translation data, message
rebuilding, font extraction, and renderer hook assumptions independently testable.

## 1. Compact custom-character stream

Wizardry VI's audited retail message corpus uses no decoded bytes at or above
`0x80`.  The Korean build can therefore reserve high-bit bytes for custom glyphs
without colliding with existing English/control data.

The current stream format is `w6-highbit-pair-v1`:

```text
ASCII/control byte: 00..7F              -> one decoded byte
custom glyph index N:
    lead  = 80 + floor(N / 128)
    trail = 80 + (N mod 128)            -> two decoded bytes
```

The pair namespace can represent 16,384 indices.  The current renderer budget is
conservatively capped at **2,048 custom glyphs** until the persistent screen-cell
encoding is proven at runtime.  The codebook contains only non-ASCII characters
actually used by the translations; it does not allocate all 11,172 Hangul
syllables.

Spreadsheet byte notation such as `<0x15>` remains one literal byte.  Literal
`<0x80>`..`<0xFF>` tokens are rejected because they collide with the custom-pair
namespace.

Tools:

- `korean/tools/korean_codec.py`
- `korean/tools/build_translation_codebook.py`

## 2. Translation-corpus headroom

The current partial Wizardry VI Messages translation export was audited with the
compact codec:

- translated rows: 937 in the local export used for this audit
- distinct non-ASCII characters: **439**
- maximum encoded translated fragment: **46 bytes**
- maximum logical glyph count in one translated fragment: **26**
- encoding failures: **0**
- remaining headroom under the 2,048-glyph runtime budget: **1,609**

The local export can lag the live sheet by a row; the authoritative W7-reuse
classification remains the separately audited sheet result.  These counts are
capacity evidence, not a new translation-status count.

For a broader upper-bound reference, the complete current Wizardry VII Messages
and Scenario translations contain **1,134 distinct non-ASCII characters**.  Of
those, 1,133 are letter characters and the only other observed custom symbol is
`×`.  This strongly suggests that a 2,048-glyph W6 budget is practical, but the
final W6 CSV must still pass the build-time limit check.

## 3. Galmuri7 compact glyph table

`korean/fonts/build_galmuri7_bitmap_table.py` uses the same KBITX decoding method
already proven in the Wizardry VII DOS work:

1. base64 decode the KBITX `d` payload (padding restored when necessary);
2. read ULEB128 height and width;
3. decode the KBITX run-length pixel stream;
4. select only codepoints present in the W6 codebook;
5. convert each glyph to a 7x7 monochrome bitmap; and
6. emit an 8-byte game cell: seven bitmap rows plus one blank row.

The output table is therefore:

```text
offset = codebook_index * 8
size   = custom_glyph_count * 8
```

For 2,048 glyphs the maximum table size is 16 KiB.  A typical W6 translation is
expected to be much smaller.  Galmuri7 itself is not vendored by this repository;
the tool accepts a locally supplied official `Galmuri7.kbitx`.

The codebook is not hard-coded to Hangul.  Any non-ASCII character is legal in
the stream if the supplied Galmuri KBITX contains a drawable glyph for it.

## 4. WROOT text path: audited retail offsets

`korean/tools/audit_text_renderer.py` verifies the original retail signatures.
WROOT is an MZ executable with a `0x200`-byte header.  Static-disassembly file
offsets must therefore not be confused with load-module CS offsets.

| Purpose | WROOT file offset | loaded CS offset |
|---|---:|---:|
| one-character WFONT0 writer | `0x24B7` | `0x22B7` |
| WFONT0 NUL-string loop | `0x26E9` | `0x24E9` |
| WFONT1..4 NUL-string loop | `0x271D` | `0x251D` |
| display driver entry0 far call | `0x25B0` | `0x23B0` |
| refresh entry1 far call | `0x2E5C` | `0x2C5C` |
| refresh entry0 far call | `0x2E69` | `0x2C69` |

Both string loops currently advance their source pointer by exactly one byte.
They must become high-bit-pair aware so one custom pair advances the visible
cursor by one logical glyph.

## 5. EGA.DRV text path

The audited EGA driver is a COM image loaded at `0x0100`.

- COM `0x0103` is entry0 and reaches the WFONT0 renderer at `0x029A`.
- The WFONT0 path computes `character * 8` and reads the WFONT0 segment pointer
  from `CS:0x0155`.
- COM `0x0107` is entry1 and reaches the WFONT1..4 renderer at `0x053A`.
- The WFONT1..4 path computes `character * 32` and uses segment pointers at
  `CS:0x0159`, `0x015D`, `0x0161`, and `0x0165`.

This confirms where an expanded/custom glyph source must join the existing EGA
draw path.  It also confirms that simply replacing `WFONT0.EGA` cannot provide
a complete Korean set.

## 6. Resident space available in WROOT

The retail WROOT contains one large continuous zero-filled run:

```text
file: 0x4772 .. 0xFF82 (exclusive)
CS:   0x4572 .. 0xFD82 (exclusive)
size: 47,120 bytes
```

That is enough room for a small 16-bit decoder and a compact glyph table of the
size expected from the W6 translation corpus.  Any executable patch must still
prove that this region is truly resident and not used as a runtime overlay or
scratch area before relying on it.

## 7. Persistent screen-cell problem

A temporary-font-slot renderer alone is unsafe.  WROOT stores a 16-bit cell word
for later `refreshwindow` repaint.  If multiple Korean characters all store the
same temporary ASCII slot, a repaint can redraw them as the wrong glyph.

The audited cell format provides a promising route:

- WFONT0 cells use low nibble `AH & 0x0F == 0`;
- WFONT1..4 cells use low nibble `1..4`;
- refresh currently rejects other font values.

A candidate design is to reserve low nibble `0xF` as a custom-cell sentinel and
store a custom index in the remaining cell bits.  With AL plus the high nibble
of AH, up to 12 index bits could theoretically be retained in the existing
16-bit cell.

**This is a design under proof, not a committed runtime format.**  WFONT0 style
bits also live in the high half of the cell, so custom-cell styling and repaint
semantics must be traced before this encoding is adopted.  The current 2,048
codebook limit therefore remains intentionally conservative.

## 8. Required runtime patch sequence

Before the first Korean smoke patch is considered safe:

1. prove the WROOT zero cave is resident for all relevant overlays;
2. patch both one-byte string loops to consume a high-bit pair as one glyph;
3. preserve custom glyph identity in the cell buffer rather than aliasing one
   temporary font slot;
4. patch `refreshwindow` to recognize and redraw the custom cell format;
5. connect the custom glyph index to the compact Galmuri7 table;
6. audit width/count/centering/wrapping helpers for raw-byte assumptions;
7. add original-byte guards and fixed-size/hash tests; and
8. only then run a DOSBox smoke test with one menu label and one message.

The translation CSV/codebook format should not need to change while these
runtime details are developed.
