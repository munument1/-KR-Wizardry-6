#!/usr/bin/env python3
"""Bit-exact MSG.DBS decode -> Huffman encode round-trip verifier.

This is the first reinsertion safety gate for the Wizardry VI Korean patch.
It derives an encoder directly from the retail `MISC.HDR` decode tree, walks all
message records referenced by `MSG.HDR`, decodes them, re-encodes the original
bytes, and requires every reconstructed record to match byte-for-byte.

When `--output` is supplied, the tool clones the original MSG.DBS and replaces
every referenced record with its reconstructed form.  This deliberately
preserves the unreferenced tail bytes in the final 1 KiB bank, so a successful
unmodified run produces an exact file identity rather than merely a functional
one.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

BANK_SIZE = 1024


def resolve_data_file(gamedata: Path, canonical_name: str) -> Path:
    direct = gamedata / canonical_name
    if direct.exists():
        return direct
    wanted = canonical_name.casefold()
    for child in gamedata.iterdir():
        if child.is_file() and child.name.casefold() == wanted:
            return child
    raise FileNotFoundError(canonical_name)


def load_tree(path: Path) -> list[tuple[int, int]]:
    data = path.read_bytes()
    if len(data) % 4:
        raise ValueError(f"MISC.HDR size is not a multiple of 4: {len(data)}")
    return [struct.unpack_from("<hh", data, i) for i in range(0, len(data), 4)]


def build_codes(nodes: list[tuple[int, int]]) -> dict[int, tuple[int, ...]]:
    codes: dict[int, tuple[int, ...]] = {}
    visiting: set[int] = set()

    def walk(node_index: int, path: tuple[int, ...]) -> None:
        if node_index in visiting:
            raise ValueError(f"Huffman tree cycle at node {node_index}")
        if not 0 <= node_index < len(nodes):
            raise ValueError(f"Huffman node outside tree: {node_index}")
        visiting.add(node_index)
        left, right = nodes[node_index]
        for bit, child in ((0, left), (1, right)):
            child_path = path + (bit,)
            if child >= 0:
                value = child & 0xFF
                previous = codes.get(value)
                if previous is not None and previous != child_path:
                    raise ValueError(f"duplicate Huffman leaf for byte 0x{value:02X}")
                codes[value] = child_path
            else:
                walk(-child, child_path)
        visiting.remove(node_index)

    walk(0, ())
    return codes


def decode(nodes: list[tuple[int, int]], bitstream: bytes, decoded_len: int) -> bytes:
    out = bytearray()
    node_index = 0
    bit_pos = 0
    while len(out) < decoded_len:
        if bit_pos // 8 >= len(bitstream):
            raise ValueError("compressed bitstream ended before decoded_len")
        bit = (bitstream[bit_pos // 8] >> (7 - (bit_pos % 8))) & 1
        bit_pos += 1
        child = nodes[node_index][bit]
        if child >= 0:
            out.append(child & 0xFF)
            node_index = 0
        else:
            node_index = -child
    return bytes(out)


def encode(codes: dict[int, tuple[int, ...]], raw: bytes) -> bytes:
    bits: list[int] = []
    for value in raw:
        try:
            bits.extend(codes[value])
        except KeyError as exc:
            raise ValueError(f"byte 0x{value:02X} has no code in MISC.HDR") from exc
    out = bytearray((len(bits) + 7) // 8)
    for bit_pos, bit in enumerate(bits):
        if bit:
            out[bit_pos // 8] |= 1 << (7 - (bit_pos % 8))
    return bytes(out)


def parse_ranges(hdr: bytes) -> list[tuple[int, int, int, int]]:
    if len(hdr) < 2 or len(hdr) % 2:
        raise ValueError("invalid MSG.HDR length")
    words = struct.unpack(f"<{len(hdr) // 2}H", hdr)
    count = words[0]
    if len(words) < 1 + count * 3:
        raise ValueError("truncated MSG.HDR range table")
    ranges: list[tuple[int, int, int, int]] = []
    pos = 1
    for _ in range(count):
        start_id, bank_offset, packed = words[pos : pos + 3]
        pos += 3
        ranges.append((start_id, (packed >> 8) & 0xFF, bank_offset, packed & 0xFF))
    return ranges


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def roundtrip(gamedata: Path) -> tuple[bytes, dict[str, int]]:
    nodes = load_tree(resolve_data_file(gamedata, "MISC.HDR"))
    codes = build_codes(nodes)
    hdr = resolve_data_file(gamedata, "MSG.HDR").read_bytes()
    original = resolve_data_file(gamedata, "MSG.DBS").read_bytes()
    if len(original) % BANK_SIZE:
        raise ValueError("MSG.DBS is not bank-aligned")

    rebuilt = bytearray(original)
    ranges = parse_ranges(hdr)
    message_count = 0
    mismatches = 0
    first_record = len(original)
    last_record_end = 0

    for start_id, bank, bank_offset, id_span in ranges:
        pos = bank * BANK_SIZE + bank_offset
        for delta in range(id_span + 1):
            message_id = start_id + delta
            message_count += 1
            first_record = min(first_record, pos)
            if not 0 <= pos < len(original):
                raise ValueError(f"message {message_id}: pointer outside MSG.DBS")
            record_len = original[pos]
            end = pos + 1 + record_len
            if end > len(original):
                raise ValueError(f"message {message_id}: record overruns MSG.DBS")

            if record_len == 0:
                rebuilt_record = b"\x00"
            else:
                payload = original[pos + 1 : end]
                decoded_len = payload[0]
                raw = decode(nodes, payload[1:], decoded_len)
                encoded = encode(codes, raw)
                rebuilt_payload = bytes([decoded_len]) + encoded
                if len(rebuilt_payload) > 0xFF:
                    raise ValueError(f"message {message_id}: rebuilt payload exceeds 255 bytes")
                rebuilt_record = bytes([len(rebuilt_payload)]) + rebuilt_payload

            original_record = original[pos:end]
            if rebuilt_record != original_record:
                mismatches += 1
                raise ValueError(
                    f"message {message_id}: round-trip mismatch at 0x{pos:X}: "
                    f"{original_record.hex()} != {rebuilt_record.hex()}"
                )
            rebuilt[pos:end] = rebuilt_record
            last_record_end = max(last_record_end, end)
            pos = end

    stats = {
        "message_count": message_count,
        "mismatches": mismatches,
        "huffman_leaves": len(codes),
        "first_record": first_record,
        "last_record_end": last_record_end,
        "unreferenced_tail": len(original) - last_record_end,
    }
    return bytes(rebuilt), stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    original_path = resolve_data_file(args.gamedata, "MSG.DBS")
    original = original_path.read_bytes()
    rebuilt, stats = roundtrip(args.gamedata)

    print(f"Messages: {stats['message_count']}")
    print(f"Huffman leaves: {stats['huffman_leaves']}")
    print(f"Record mismatches: {stats['mismatches']}")
    print(f"Referenced record span: 0x{stats['first_record']:X}-0x{stats['last_record_end']:X}")
    print(f"Unreferenced tail bytes: {stats['unreferenced_tail']}")
    print(f"Original SHA-256: {sha256(original)}")
    print(f"Rebuilt  SHA-256: {sha256(rebuilt)}")
    print(f"Whole-file identical: {rebuilt == original}")

    if rebuilt != original:
        raise SystemExit("round-trip failed: rebuilt MSG.DBS differs")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(rebuilt)
        print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
