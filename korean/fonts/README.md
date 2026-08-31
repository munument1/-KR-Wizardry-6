# Korean font plan

## Selected base font

The Korean localization uses **Galmuri7 (갈무리7)** as the baseline Hangul pixel typeface.

Galmuri is distributed under the **SIL Open Font License 1.1 (OFL-1.1)**. The font binary is not required to be committed at this stage. Font-generation tools should accept a locally supplied Galmuri7 font path and generate only the game-specific glyph data needed by the patch workflow.

## Wizardry VI constraints

The original DOS EGA fonts are fixed 8x8 cells:

- `WFONT0.EGA`: 128 glyphs, 1bpp, 8 bytes per glyph
- `WFONT1.EGA` ... `WFONT4.EGA`: 128 glyphs, four EGA planes, 32 bytes per glyph

A full Korean set cannot fit in the original 128 single-byte slots.  The W6
localization therefore uses a **compact used-glyph codebook** rather than a
full-Unicode table:

1. ASCII/control bytes remain one byte and compatible with retail data;
2. non-ASCII characters used by the translation receive dense two-high-byte codes;
3. the current runtime budget is 2,048 custom glyphs (the pair namespace itself is larger);
4. only those codebook characters are extracted from Galmuri7; and
5. the future WROOT renderer consumes a two-byte custom code as one logical cell.

The codebook is not limited to Hangul.  Punctuation or symbols are allowed when
the supplied Galmuri7 KBITX contains the requested glyph.  This avoids changing
the stream format if a translation later needs a symbol such as `×`.

## KBITX builder

`build_galmuri7_bitmap_table.py` uses the KBITX decoding path already validated
in the Wizardry VII DOS localization: base64 payload, ULEB128 dimensions, and
KBITX run-length pixel decoding.  It does not depend on a system TTF renderer.

For each codebook character it emits exactly 8 bytes:

- rows 0..6: Galmuri7's 7x7 monochrome pixels in bits 7..1;
- row 7: blank padding row.

Therefore `offset = codebook_index * 8`.  At the conservative 2,048-glyph cap
the complete custom table is at most 16 KiB.

Example:

```bash
python korean/fonts/build_galmuri7_bitmap_table.py \
  --input /path/to/Galmuri7.kbitx \
  --codebook output/wiz6_codebook.json \
  --output output/wiz6_glyphs.bin \
  --metadata output/wiz6_glyphs.json
```

The generated bitmap is a local build product.  Do not commit the upstream font
file or a game-derived patched executable.

## Renderer caution

Do not assume that simply replacing `WFONT0.EGA` or repeatedly overwriting one
reserved ASCII slot is sufficient.  WROOT stores character/font information in
a 16-bit cell buffer and later redraws it during window refresh.  The custom
glyph index must therefore remain recoverable from that persistent cell state.
`docs/KOREAN_COMPACT_RENDERER_PLAN.md` records the currently audited hook points
and the still-unproven custom-cell design.

## Licensing / naming

If any modified or derived font software is redistributed, preserve the OFL 1.1 notice and comply with the reserved font-name condition. Game-specific derived bitmap data should use a neutral project name such as `wiz6_ko_glyphs` rather than presenting itself as a modified font named `Galmuri`.
