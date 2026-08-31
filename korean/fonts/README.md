# Korean font plan

## Selected base font

The Korean localization uses **Galmuri7 (갈무리7)** as the baseline Hangul pixel typeface.

Galmuri is distributed under the **SIL Open Font License 1.1 (OFL-1.1)**. The font binary is not required to be committed at this stage. Font-generation tools should accept a locally supplied Galmuri7 font path and generate only the game-specific glyph data needed by the patch workflow.

## Wizardry VI constraints

The original DOS EGA fonts are fixed 8x8 cells:

- `WFONT0.EGA`: 128 glyphs, 1bpp, 8 bytes per glyph
- `WFONT1.EGA` ... `WFONT4.EGA`: 128 glyphs, four EGA planes, 32 bytes per glyph

A full Korean set cannot fit in the original 128 single-byte slots. The intended implementation remains the Wizardry VII-style approach:

1. keep ASCII/control bytes compatible;
2. reserve a 2-byte Korean code space;
3. intercept character iteration so one 2-byte Korean code is one logical glyph;
4. map that code to an external/expanded Hangul glyph store;
5. rasterize Galmuri7 into the 8x8 visual cell used by Wizardry VI;
6. make width, centering and line wrapping count logical glyphs rather than raw bytes.

## Rasterization rule

The first prototype should render Galmuri7 into an **8x8 target cell** without resampling blur. Pixel alignment and baseline offset should be tuned with generated contact sheets before any executable patch is attempted.

Do not assume that simply replacing `WFONT0.EGA` is enough: the original WFONT tables contain only 128 entries, so the runtime renderer must be extended for Hangul.

## Licensing / naming

If any modified or derived font software is redistributed, preserve the OFL 1.1 notice and comply with the reserved font-name condition. Game-specific derived bitmap data should use a neutral project name such as `wiz6_ko_glyphs` rather than presenting itself as a modified font named `Galmuri`.
