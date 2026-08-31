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
