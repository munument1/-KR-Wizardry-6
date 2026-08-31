# Wizardry VI DOS Korean MSG complete-build audit

Date: 2026-08-31  
Branch: `korean-localization`

## Input contract

The completed Messages translation CSV is treated as data, not as a trusted
binary patch. `build_korean_messages.py` first re-decodes all 5,161 retail
message IDs and verifies that every CSV `source_text` round-trips byte-for-byte
to the retail decoded record before accepting any translation.

The current completed CSV passes with **0 source mismatches**.

## Completed translation corpus

Current final Messages corpus:

- indexed message IDs: **5,161**
- non-empty translated rows: **4,720**
- encoded messages whose bytes differ from retail: **4,402**
- empty/reserved decoded messages: **441** (kept empty)
- compact custom glyphs: **982 / 2,048**
- glyph headroom: **1,066**
- maximum encoded translation fragment: **66 bytes** (`message_id 9502`)
- maximum logical glyph count in one fragment: **40**
- encoding failures: **0**

The compact codebook therefore remains well inside the current 11-bit persistent
screen-cell budget and the MSG decoded-length byte remains well below 255.

## 1KB bank safety correction

A naive consecutive rebuild is semantically decodable but is not faithful to the
retail runtime lookup rule. `WROOT` finds one `MSG.HDR` range, loads the range's
1KB page, then walks preceding record starts by adding `1 + record_len`.

The retail data has **zero** cases where a later record start in one range moves
into a different bank. The final record payload itself may cross a bank boundary;
`WROOT` explicitly loads the next page while copying that final record.

The completed Korean corpus initially produced 63 unsafe range-start crossings
when packed consecutively. The rebuilder now inserts padding before a range when
necessary so every record start covered by that range remains in its `MSG.HDR`
bank. Final Korean build:

- `MSG.DBS`: **83,968 bytes**
- banks: **82**
- inter-range padding: **6,391 bytes**
- record-start bank crossings: **0**
- all 5,161 rebuilt messages decode back to the intended encoded bytes: **yes**

## WROOT page-count check

82 banks do not require an executable limit patch. The retail WROOT page loader
(at the routine documented around logical `0x06AA`, file `0x08AA`) uses the
requested page number directly:

1. compare against its four-entry page cache;
2. compute file offset as `page << 10`;
3. seek to that offset in `MSG.DBS`;
4. read exactly `0x400` bytes.

The four entries are a cache size, not a total-bank limit. No comparison against
80 / `0x50` exists in this page-loading path. `MSG.HDR` stores the bank as an
8-bit field, so bank indexes through 255 remain structurally representable.

## Reproducible build

Use:

```text
python korean/tools/build_korean_messages.py \
  --gamedata <retail game directory> \
  --translations Wizardry6_Messages_Korean_Complete.csv \
  --output-dir <local output directory>
```

The output directory contains:

- `MSG.DBS`
- `MSG.HDR`
- `MISC.HDR`
- `codebook.json`
- `message_overrides.csv`
- `build_report.json`

These are generated from retail game data and/or the translation corpus and are
not committed as distributable game files.

Current reproducible hashes for the completed Messages build are:

```text
MSG.DBS   f6e067954bece5058a8934b0196560f8ca2d886d8047a1fdba7fb3e74c024750
MSG.HDR   9142ef36743c8ff9fe873a08408f51219faf45575c48dc96931759f3ffd38297
MISC.HDR  5f4ab170bde3ed82dd4231d03ea7bc727f35278c7d75b8e679482510eebab218
```

## Safety gates retained

- no-change `original-tree` rebuild remains bit-exact for all three retail files;
- empty decoded records remain canonical `01 00` records;
- decoded fragment length must be <=255;
- compressed payload length must be <=255;
- Huffman rebuild exposes all 256 byte values;
- `MSG.HDR` range ID semantics are unchanged;
- record-start bank crossings must be zero;
- bank index must fit the 8-bit header field;
- rebuilt data must decode back exactly before files are written.

The next independent milestone is the executable renderer: consume the compact
high-bit pairs as one glyph, persist the 11-bit custom index in the screen cell,
and repaint Galmuri7 glyphs safely through the WFONT0/EGA path.
