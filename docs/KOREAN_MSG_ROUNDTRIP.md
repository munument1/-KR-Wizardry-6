# Wizardry VI Korean localization: MSG bit-exact round-trip

Date: 2026-08-31  
Branch: `korean-localization`

## Result

The retail `MSG.DBS` message stream can be decoded and re-encoded with the existing `MISC.HDR` Huffman tree **bit-exactly**.

Validated against the project's audited original DOS data:

- message records walked from `MSG.HDR`: **5,161**
- Huffman byte leaves recovered from `MISC.HDR`: **122**
- record mismatches after decode -> encode: **0**
- referenced record span: `0x00000` through `0x13D79` (`last_record_end = 0x13D7A`)
- `MSG.DBS` total size: `0x14000` (80 x 1024-byte banks)
- final unreferenced tail: **646 bytes**
- original SHA-256: `c5011224fbd16b1dd1a85117f760f25b4efd2232a84c51dfb88547a283099213`
- rebuilt SHA-256: `c5011224fbd16b1dd1a85117f760f25b4efd2232a84c51dfb88547a283099213`
- whole-file identity: **true**

## Encoder derivation

`MISC.HDR` is already a complete prefix tree. The encoder does not need to guess frequencies or rebuild a new tree for the unmodified test. It walks node 0 recursively:

- left child -> append bit `0`
- right child -> append bit `1`
- non-negative child -> leaf byte (`value & 0xFF`)
- negative child -> recurse into node `-value`

This creates a unique bit sequence for every byte present in the tree. Encoded bits are packed MSB-first, matching the decoder.

All original message payloads reproduce exactly, including the final padding bits of each compressed record.

## Why the final 646 bytes are preserved

All referenced records form one continuous prefix of `MSG.DBS`, ending at `0x13D7A`. The remaining 646 bytes in the final 1 KiB bank are not referenced by any `MSG.HDR` range and are mostly non-zero stale/padding data.

For an exact identity test, `roundtrip_messages.py` clones the original file and overwrites every referenced record with its regenerated record. The unreferenced tail remains untouched. This gives both:

1. bit-exact proof for every referenced message record; and
2. whole-file SHA-256 identity for the no-change case.

Future translated rebuilds may choose a deterministic policy for unused bank tail bytes, but that should be separate from this baseline identity test.

## Record limits that matter for Korean

The current record format has two one-byte size fields:

- `record_len`: maximum payload length `255` bytes
- `decoded_len`: maximum decoded message-fragment length `255` bytes

A 2-byte Hangul encoding therefore makes byte-length pressure more important than in English. Before translated reinsertion, the builder must validate each individual message ID against these limits. Do not merge IDs merely for editorial convenience: IDs/ranges are part of the runtime lookup structure.

## Tool

`korean/tools/roundtrip_messages.py`

Example:

```bash
python korean/tools/roundtrip_messages.py --gamedata gamedata
python korean/tools/roundtrip_messages.py --gamedata gamedata --output output/MSG.DBS
```

The output form is safe only as a locally generated file from the user's own game data. Do not commit the rebuilt commercial database.

## Next reinsertion step

The next builder should accept edited encoded message bytes, repack referenced records, and regenerate `MSG.HDR` bank/offset starts while preserving each range's message-ID semantics. It must reject any individual fragment whose decoded or compressed payload exceeds the one-byte format limits.

## Integrated container rebuilder

`korean/tools/rebuild_message_files.py` now handles the three message-container files together.

### `original-tree` identity mode

With no overrides it:

1. decodes all 5,161 indexed IDs with the retail `MISC.HDR`;
2. encodes them with the inverse retail tree;
3. regenerates every `MSG.HDR` range start from the repacked record stream;
4. preserves the 646-byte unreferenced retail tail only for this no-change safety mode; and
5. requires `MSG.DBS`, `MSG.HDR`, and `MISC.HDR` to be byte-identical to the originals.

The audited retail build passes all three identity checks.

### Empty/reserved IDs

There are **441 decoded-empty indexed messages**. They are not zero-length records. Every one uses the canonical two-byte record form:

```text
01 00
^^ ^^
|  +-- decoded_len = 0
+----- record_len = 1
```

No indexed message in the audited build uses `record_len = 0`. The rebuilder therefore emits `01 00` for an empty decoded message. These rows can remain untranslated/empty; their message IDs and range membership are still preserved.

### `rebuild-tree` mode

For translated data the tool can generate a fresh `MISC.HDR` tree weighted from the final encoded message bytes. All **256 byte values** are deliberately present as leaves so a future two-byte Korean code space can use bytes above `0x7F`.

Validation with unchanged English messages produced:

- 256 encodable byte values
- 255 reachable internal Huffman nodes plus one unused/padded node in the fixed 256-node file
- 78 banks for `MSG.DBS`
- successful decode validation of all 5,161 message IDs

A separate stress test replaced four harmless test messages with 64-byte fragments covering `0x00` through `0xFF`. The rebuilt tree encoded and decoded every byte value exactly. The resulting database used 79 banks.

This does **not** mean an arbitrary 255-byte fragment will always fit. `record_len` includes the one-byte `decoded_len` plus the compressed bitstream, so rare-symbol-heavy text can exceed the 255-byte compressed-payload limit even when decoded length is legal. The builder rejects both limits explicitly.

### Local command examples

```bash
# Exact no-change proof
python korean/tools/rebuild_message_files.py \
  --gamedata gamedata \
  --mode original-tree \
  --output-dir output/identity

# Rebuild Huffman tree and bank/index layout
python korean/tools/rebuild_message_files.py \
  --gamedata gamedata \
  --mode rebuild-tree \
  --output-dir output/rebuilt

# Feed already encoded byte overrides (CSV columns: message_id,encoded_bytes_hex)
python korean/tools/rebuild_message_files.py \
  --gamedata gamedata \
  --mode rebuild-tree \
  --overrides encoded_overrides.csv \
  --output-dir output/korean
```

The generated retail-derived files are local build products and must not be committed.

## Automated tests

`korean/tests/test_message_rebuilder.py` is retail-data-free and verifies:

- canonical `01 00` empty records;
- 256-byte Huffman coverage;
- encode/decode of all byte values in legal-size fragments;
- identity-tail preservation logic; and
- decoded/compressed one-byte length guards.
