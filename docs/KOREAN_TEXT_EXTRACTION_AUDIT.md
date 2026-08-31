# Wizardry VI Korean Text Extraction Audit

Date: 2026-08-31

This document records the current static extraction boundary for the DOS Korean localization branch. Original retail game binaries are **not** committed to this repository; all offsets below were validated against the user's local retail data and the hashes recorded in the Source Manifest sheet.

## 1. Source validation

The local copies of `WROOT.EXE`, `MSG.DBS`, `MSG.HDR`, `MISC.HDR`, `SCENARIO.DBS`, `SCENARIO.HDR` and the other major game assets match the SHA-256 values in the Wizardry 6 Source Manifest. The extraction results below therefore refer to the same source build used by the translation sheets.

## 2. MSG.DBS / MSG.HDR / MISC.HDR

### Structure and validation

- `MSG.HDR`: 718 message ranges.
- `MSG.DBS`: 80 banks, 1024 bytes per bank.
- Extracted individual message IDs: **5,161**.
- Unique message IDs: **5,161**.
- Duplicate message IDs: **0**.
- Duplicate record pointers: **0**.
- Record/bank boundary errors: **0**.

The localization sheet must keep one row per original message ID. Joined range text is useful only as a preview and must never replace the ID-level representation needed for reinsertion.

### Lossless source representation

`korean/tools/extract_messages.py` writes printable ASCII literally and non-printable bytes as `<0xNN>`. Literal backslashes are escaped. A `source_bytes_hex` column is also emitted for byte-level verification.

A previous sheet-generation pass stripped leading/trailing spaces and allowed Google Sheets to coerce numeric-looking strings. That destroys exact reinsertion data. The current sheet was repaired so strings such as ` HP`, `CC `, `012`, `0300`, padded menu labels and control-code-bearing text are preserved as explicit strings.

`readable_preview` is intentionally normalized for people and must not be used as the binary source.

### Wizardry VII reuse validation

Current W6 message match status counts:

- `W7_ID_EXACT`: 639
- `W7_TEXT_EXACT`: 299
- `W7_TEXT_AMBIGUOUS`: 5
- `UNMATCHED`: 4,218
- Automatically reusable exact translations: **938**

Empty source strings are deliberately excluded from automatic exact matching. Matching empty rows by ID would create false positives. A small set of W7 translations containing significant leading/trailing spaces or numeric-only text was also restored byte-for-text faithfully in the W6 sheet.

## 3. SCENARIO.DBS

### Item table

- Base: `0x0380`
- Record size: `0x4A` (74 bytes)
- Slots inspected: 483
- Display-name field: `+0x00`, capacity 16 bytes, C string
- Non-empty/plausible item names in the current W6 sheet: 452

### Monster table

- Base: `0x154E6`
- Record size: `0xDE` (222 bytes)
- Actual W6 record count: **251** (`0..250`)
- Name fields:
  - `+0x02`: singular, 16 bytes
  - `+0x12`: plural, 16 bytes
  - `+0x22`: short/generic singular, 16 bytes
  - `+0x32`: short/generic plural, 16 bytes
- Structured monster strings currently present: 741

An earlier 256-slot assumption is unsafe for Wizardry VI: records after 250 begin reading the following structure as if it were a monster. The new audit tool therefore uses 251 records.

### NPC / special-encounter table

A previously unextracted fixed table was identified immediately after the monster region:

- Base: `0x22ED0`
- Record size: `0x8E` (142 bytes)
- Record count: **30**
- Display-name field: `+0x00`, capacity 16 bytes, C string
- Exact next-section boundary: `0x23F74`

The 30 names include `COSMIC FORGE`, `L'MONTES`, `TOLL TROLL`, `VICAR'S GHOST`, `AMAZULU QUEEN`, `THE SIREN`, `QUEEN'S GHOST`, `R E B E C C A` and others. These rows have been added to the W6 Scenario translation sheet.

Only `* B E L A *` had an exact text counterpart in the current W7 Scenario data; it is prefilled as `* 벨 라 *` with a review status because the W7 match comes from a monster-name category rather than the W6 NPC table.

### Residual ASCII audit

After excluding known item, monster and NPC name fields, a conservative printable-run scan still finds many apparent ASCII fragments. Most are binary/map/stat data that happen to fall in the printable range. No additional block has yet been promoted to a structured translation table solely from a `strings`-style scan. Any future additions must be supported by record structure or code references.

## 4. WROOT.EXE and W*.OVR

`korean/tools/scan_binary_strings.py` performs a conservative ASCII audit and does **not** treat every printable run as translatable text. The strongest current user-visible candidates are all in `WROOT.EXE`:

| Offset | Text | Initial classification |
| ---: | --- | --- |
| `0x021BE` | `Unable to load display driver` | runtime error |
| `0x02339` | `Unable to allocate sufficient memory to run.` | runtime error |
| `0x0243D` | `I/O error loading font` | runtime error |
| `0x02BB8` | `I/O error loading Misc. table.` | runtime error |
| `0x03105` | `Invalid font in refreshwindow` | runtime error |
| `0x10506` | `INSERT SAVEGAME DISK` | DOS/UI prompt |
| `0x1051B` | `INSERT DISK (^)` | DOS/UI prompt |
| `0x1052B` | `INTO DRIVE ^` | DOS/UI prompt |
| `0x10538` | `PRESS X` | DOS/UI prompt |
| `0x105BB` | `Error %d loading overlay: %s$` | formatted runtime error |
| `0x105F0` | `8087/80287 is required!` | hardware/runtime error |
| `0x1060D` | `Too many args.` | runtime error |

The other obvious OVR tail strings are predominantly filenames, resource names or internal references. Static xref/call-site tracing is still required before patching executable strings, especially where formatting tokens or terminal markers are present.

## 5. Image text inventory

The translation workbook now contains an `Image Text Inventory` tab. Priority visual assets include the `TITLEPAG` variants and `CREDITS.PIC`; `GRAVEYRD` and `DRAGONSC` variants are retained for visual review. Portrait sheets are inventoried but are not current text targets.

This is only an inventory. Embedded bitmap text should be confirmed with the existing image decoders / format analysis before any image replacement work begins.

## 6. Unsafe or failed approaches to avoid

- Do not use a raw `strings` dump as the translation list. 16-bit x86 code and structured binary data create many false positives.
- Do not use `.strip()` on the canonical MSG source text. Leading/trailing spaces can be layout/control data.
- Do not allow spreadsheet software to convert numeric-looking source strings to numbers. `012` and `12` are not equivalent for reinsertion.
- Do not auto-match empty strings against W7.
- Do not use 256 Wizardry VII-style monster slots for this W6 SCENARIO layout; W6's structured monster block ends after record 250.
- Do not replace individual message IDs with concatenated range text.

## 7. Next static-analysis steps

1. Trace xrefs/call sites for the 12 `WROOT.EXE` candidate strings and determine exact display semantics and writable capacity.
2. Continue looking for encoded/fixed UI labels that are not visible as plain ASCII.
3. Decode and visually inspect the inventoried image assets for embedded English.
4. Keep translation extraction and terminology cleanup ahead of Korean renderer work.
5. Only after the text inventory is stable, move to font/2-byte encoding, width calculation, wrapping and reinsertion.
