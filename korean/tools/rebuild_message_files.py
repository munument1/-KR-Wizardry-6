#!/usr/bin/env python3
"""Rebuild Wizardry VI MSG.DBS / MSG.HDR / MISC.HDR from message bytes.

Optional overrides are already-encoded decoded-message bytes keyed by message_id.
This module deliberately keeps Unicode/font policy separate from the container.

Modes:
- original-tree: reuse retail MISC.HDR. With no overrides, output must be bit-exact.
- rebuild-tree: build a full 256-byte Huffman tree and repack messages.

Runtime safety rule:
A MSG.HDR range identifies one 1KB bank and WROOT walks sub-record starts inside
that bank. The final record payload may cross into the next bank, but no later
record start in the same range may do so. Repacked non-identity data therefore
aligns a range to the next bank whenever its last record start would leave the
range's starting bank.
"""
from __future__ import annotations

import argparse
import csv
import heapq
import math
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

BANK_SIZE = 1024
MISC_NODE_COUNT = 256
MAX_BANKS = 256


def resolve_data_file(gamedata: Path, canonical_name: str) -> Path:
    direct = gamedata / canonical_name
    if direct.exists():
        return direct
    wanted = canonical_name.casefold()
    for child in gamedata.iterdir():
        if child.is_file() and child.name.casefold() == wanted:
            return child
    raise FileNotFoundError(canonical_name)


def load_nodes(data: bytes) -> list[tuple[int, int]]:
    if len(data) % 4:
        raise ValueError("Huffman tree size is not a multiple of 4")
    return [struct.unpack_from("<hh", data, i) for i in range(0, len(data), 4)]


def build_codes(nodes: list[tuple[int, int]]) -> dict[int, tuple[int, ...]]:
    codes: dict[int, tuple[int, ...]] = {}
    visiting: set[int] = set()

    def walk(index: int, path: tuple[int, ...]) -> None:
        if index in visiting:
            raise ValueError(f"Huffman cycle at node {index}")
        if not 0 <= index < len(nodes):
            raise ValueError(f"Huffman node outside tree: {index}")
        visiting.add(index)
        for bit, child in ((0, nodes[index][0]), (1, nodes[index][1])):
            next_path = path + (bit,)
            if child >= 0:
                value = child & 0xFF
                if value in codes and codes[value] != next_path:
                    raise ValueError(f"duplicate leaf byte 0x{value:02X}")
                codes[value] = next_path
            else:
                walk(-child, next_path)
        visiting.remove(index)

    walk(0, ())
    return codes


def decode(nodes: list[tuple[int, int]], bitstream: bytes, decoded_len: int) -> bytes:
    out = bytearray()
    node = 0
    bit_pos = 0
    while len(out) < decoded_len:
        if bit_pos // 8 >= len(bitstream):
            raise ValueError("compressed message ended early")
        bit = (bitstream[bit_pos // 8] >> (7 - (bit_pos % 8))) & 1
        bit_pos += 1
        child = nodes[node][bit]
        if child >= 0:
            out.append(child & 0xFF)
            node = 0
        else:
            node = -child
    return bytes(out)


def encode(codes: dict[int, tuple[int, ...]], raw: bytes) -> bytes:
    bits: list[int] = []
    for value in raw:
        if value not in codes:
            raise ValueError(f"byte 0x{value:02X} is not present in Huffman tree")
        bits.extend(codes[value])
    out = bytearray((len(bits) + 7) // 8)
    for bit_pos, bit in enumerate(bits):
        if bit:
            out[bit_pos // 8] |= 1 << (7 - (bit_pos % 8))
    return bytes(out)


@dataclass(frozen=True)
class Range:
    start_id: int
    id_span: int
    bank: int
    bank_offset: int


def parse_ranges(hdr: bytes) -> tuple[list[Range], int]:
    if len(hdr) < 2 or len(hdr) % 2:
        raise ValueError("invalid MSG.HDR")
    words = struct.unpack(f"<{len(hdr) // 2}H", hdr)
    count = words[0]
    table_words = 1 + count * 3
    if len(words) < table_words:
        raise ValueError("truncated MSG.HDR")
    ranges: list[Range] = []
    pos = 1
    for _ in range(count):
        start_id, bank_offset, packed = words[pos : pos + 3]
        pos += 3
        ranges.append(Range(start_id, packed & 0xFF, (packed >> 8) & 0xFF, bank_offset))
    return ranges, table_words * 2


def extract_original_messages(
    ranges: list[Range], dbs: bytes, nodes: list[tuple[int, int]]
) -> dict[int, bytes]:
    messages: dict[int, bytes] = {}
    for entry in ranges:
        pos = entry.bank * BANK_SIZE + entry.bank_offset
        for delta in range(entry.id_span + 1):
            message_id = entry.start_id + delta
            if pos >= len(dbs):
                raise ValueError(f"message {message_id}: record pointer outside MSG.DBS")
            record_len = dbs[pos]
            end = pos + 1 + record_len
            if end > len(dbs):
                raise ValueError(f"message {message_id}: record overruns MSG.DBS")
            if record_len:
                payload = dbs[pos + 1 : end]
                messages[message_id] = decode(nodes, payload[1:], payload[0])
            else:
                messages[message_id] = b""
            pos = end
    return messages


def load_overrides(path: Path | None) -> dict[int, bytes]:
    if path is None:
        return {}
    out: dict[int, bytes] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"message_id", "encoded_bytes_hex"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("override CSV needs message_id,encoded_bytes_hex")
        for row in reader:
            message_id = int(row["message_id"])
            if message_id in out:
                raise ValueError(f"duplicate override message_id {message_id}")
            out[message_id] = bytes.fromhex(row["encoded_bytes_hex"].strip())
    return out


@dataclass
class _HNode:
    symbol: int | None = None
    left: "_HNode | None" = None
    right: "_HNode | None" = None


def generate_full_byte_tree(messages: dict[int, bytes]) -> list[tuple[int, int]]:
    frequencies = Counter(value for raw in messages.values() for value in raw)
    heap: list[tuple[int, int, _HNode]] = []
    sequence = 0
    for symbol in range(256):
        weight = frequencies.get(symbol, 0) or 1
        heapq.heappush(heap, (weight, sequence, _HNode(symbol=symbol)))
        sequence += 1
    while len(heap) > 1:
        weight_a, _seq_a, left = heapq.heappop(heap)
        weight_b, _seq_b, right = heapq.heappop(heap)
        heapq.heappush(
            heap,
            (weight_a + weight_b, sequence, _HNode(left=left, right=right)),
        )
        sequence += 1
    root = heap[0][2]

    internals: list[_HNode] = []
    index_by_object: dict[int, int] = {}

    def allocate(node: _HNode) -> None:
        if node.symbol is not None:
            return
        index_by_object[id(node)] = len(internals)
        internals.append(node)
        assert node.left is not None and node.right is not None
        allocate(node.left)
        allocate(node.right)

    allocate(root)
    if len(internals) > MISC_NODE_COUNT:
        raise ValueError(f"Huffman tree needs {len(internals)} internal nodes")

    def child_value(node: _HNode) -> int:
        if node.symbol is not None:
            return node.symbol
        return -index_by_object[id(node)]

    nodes: list[tuple[int, int]] = []
    for node in internals:
        assert node.left is not None and node.right is not None
        nodes.append((child_value(node.left), child_value(node.right)))
    nodes.extend([(0, 0)] * (MISC_NODE_COUNT - len(nodes)))
    return nodes


def serialize_nodes(nodes: list[tuple[int, int]]) -> bytes:
    if len(nodes) != MISC_NODE_COUNT:
        raise ValueError(f"MISC.HDR must serialize {MISC_NODE_COUNT} nodes")
    out = bytearray()
    for left, right in nodes:
        out.extend(struct.pack("<hh", left, right))
    return bytes(out)


def build_records(messages: dict[int, bytes], codes: dict[int, tuple[int, ...]]) -> dict[int, bytes]:
    records: dict[int, bytes] = {}
    for message_id, raw in messages.items():
        if len(raw) > 0xFF:
            raise ValueError(f"message {message_id}: decoded length {len(raw)} exceeds 255")
        if not raw:
            records[message_id] = b"\x01\x00"
            continue
        compressed = encode(codes, raw)
        payload = bytes([len(raw)]) + compressed
        if len(payload) > 0xFF:
            raise ValueError(
                f"message {message_id}: compressed payload {len(payload)} exceeds 255"
            )
        records[message_id] = bytes([len(payload)]) + payload
    return records


def _last_record_start_prefix(entry: Range, records: dict[int, bytes]) -> int:
    """Bytes from range start to its final record start (payload excluded)."""
    prefix = 0
    for delta in range(entry.id_span):
        prefix += len(records[entry.start_id + delta])
    return prefix


def find_record_start_crossings(
    ranges: list[Range], dbs: bytes
) -> list[tuple[int, int, int, int]]:
    """Return (range_index, message_id, entry_bank, actual_bank) violations."""
    violations: list[tuple[int, int, int, int]] = []
    for range_index, entry in enumerate(ranges):
        pos = entry.bank * BANK_SIZE + entry.bank_offset
        for delta in range(entry.id_span + 1):
            actual_bank = pos // BANK_SIZE
            if actual_bank != entry.bank:
                violations.append(
                    (range_index, entry.start_id + delta, entry.bank, actual_bank)
                )
            if pos >= len(dbs):
                break
            pos += 1 + dbs[pos]
    return violations


def repack(
    ranges: list[Range],
    records: dict[int, bytes],
    original_hdr: bytes,
    *,
    preserve_tail_from: bytes | None = None,
    keep_range_record_starts_in_bank: bool = True,
) -> tuple[bytes, bytes, int]:
    stream = bytearray()
    hdr_words: list[int] = [len(ranges)]
    padding_bytes = 0

    for entry in ranges:
        if keep_range_record_starts_in_bank:
            current_offset = len(stream) % BANK_SIZE
            last_start_prefix = _last_record_start_prefix(entry, records)
            if last_start_prefix >= BANK_SIZE:
                raise ValueError(
                    f"range {entry.start_id}..{entry.start_id + entry.id_span}: "
                    f"record starts span {last_start_prefix + 1} bytes and cannot fit one bank"
                )
            if current_offset and current_offset + last_start_prefix >= BANK_SIZE:
                gap = BANK_SIZE - current_offset
                stream.extend(bytes(gap))
                padding_bytes += gap

        absolute = len(stream)
        bank = absolute // BANK_SIZE
        bank_offset = absolute % BANK_SIZE
        if bank >= MAX_BANKS:
            raise ValueError(f"MSG.DBS needs bank {bank}, exceeds 8-bit bank index")
        hdr_words.extend(
            [entry.start_id, bank_offset, (bank << 8) | entry.id_span]
        )
        for delta in range(entry.id_span + 1):
            message_id = entry.start_id + delta
            stream.extend(records[message_id])

    bank_count = max(1, math.ceil(len(stream) / BANK_SIZE))
    if bank_count > MAX_BANKS:
        raise ValueError(f"MSG.DBS needs {bank_count} banks; maximum is {MAX_BANKS}")
    aligned_size = bank_count * BANK_SIZE
    if preserve_tail_from is not None:
        if len(preserve_tail_from) != aligned_size:
            raise ValueError("identity tail template size does not match rebuilt bank count")
        stream.extend(preserve_tail_from[len(stream) : aligned_size])
    else:
        stream.extend(bytes(aligned_size - len(stream)))

    table_bytes = struct.pack(f"<{len(hdr_words)}H", *hdr_words)
    if len(original_hdr) >= len(table_bytes):
        new_hdr = table_bytes + original_hdr[len(table_bytes) :]
    else:
        new_hdr = table_bytes
    return bytes(stream), new_hdr, padding_bytes


def validate_built(
    ranges: list[Range],
    hdr: bytes,
    dbs: bytes,
    nodes: list[tuple[int, int]],
    expected: dict[int, bytes],
    *,
    require_safe_range_starts: bool = True,
) -> None:
    parsed, _ = parse_ranges(hdr)
    if [(r.start_id, r.id_span) for r in parsed] != [
        (r.start_id, r.id_span) for r in ranges
    ]:
        raise ValueError("rebuilt MSG.HDR changed message-ID range semantics")
    if require_safe_range_starts:
        crossings = find_record_start_crossings(parsed, dbs)
        if crossings:
            raise ValueError(f"rebuilt MSG ranges have {len(crossings)} record-start bank crossings")
    actual = extract_original_messages(parsed, dbs, nodes)
    if actual != expected:
        for message_id in expected:
            if actual.get(message_id) != expected[message_id]:
                raise ValueError(f"rebuilt message {message_id} failed decode validation")
        raise ValueError("rebuilt messages differ")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gamedata", type=Path, required=True)
    parser.add_argument("--overrides", type=Path, help="CSV: message_id,encoded_bytes_hex")
    parser.add_argument(
        "--mode", choices=["original-tree", "rebuild-tree"], default="original-tree"
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()

    original_misc = resolve_data_file(args.gamedata, "MISC.HDR").read_bytes()
    original_hdr = resolve_data_file(args.gamedata, "MSG.HDR").read_bytes()
    original_dbs = resolve_data_file(args.gamedata, "MSG.DBS").read_bytes()
    original_nodes = load_nodes(original_misc)
    ranges, _table_bytes = parse_ranges(original_hdr)
    messages = extract_original_messages(ranges, original_dbs, original_nodes)

    overrides = load_overrides(args.overrides)
    unknown = sorted(set(overrides) - set(messages))
    if unknown:
        raise ValueError(f"override IDs not present in MSG.HDR: {unknown[:10]}")
    messages.update(overrides)

    if args.mode == "original-tree":
        nodes = original_nodes
        misc = original_misc
    else:
        nodes = generate_full_byte_tree(messages)
        misc = serialize_nodes(nodes)
    codes = build_codes(nodes)
    records = build_records(messages, codes)

    identity_mode = args.mode == "original-tree" and not overrides
    dbs, hdr, padding_bytes = repack(
        ranges,
        records,
        original_hdr,
        preserve_tail_from=original_dbs if identity_mode else None,
        keep_range_record_starts_in_bank=not identity_mode,
    )
    validate_built(
        ranges,
        hdr,
        dbs,
        nodes,
        messages,
        require_safe_range_starts=True,
    )

    crossings = find_record_start_crossings(parse_ranges(hdr)[0], dbs)
    print(f"Messages: {len(messages)}")
    print(f"Overrides: {len(overrides)}")
    print(f"Mode: {args.mode}")
    print(f"Huffman byte codes: {len(codes)}")
    print(f"MSG.DBS: {len(dbs)} bytes ({len(dbs)//BANK_SIZE} banks)")
    print(f"MSG.HDR: {len(hdr)} bytes")
    print(f"MISC.HDR: {len(misc)} bytes")
    print(f"Inter-range padding: {padding_bytes} bytes")
    print(f"Record-start bank crossings: {len(crossings)}")
    print(f"DBS identical to original: {dbs == original_dbs}")
    print(f"HDR identical to original: {hdr == original_hdr}")
    print(f"MISC identical to original: {misc == original_misc}")

    if identity_mode:
        if dbs != original_dbs or hdr != original_hdr or misc != original_misc:
            raise SystemExit("no-change original-tree rebuild must be bit-exact")

    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        (args.output_dir / "MSG.DBS").write_bytes(dbs)
        (args.output_dir / "MSG.HDR").write_bytes(hdr)
        (args.output_dir / "MISC.HDR").write_bytes(misc)
        print(f"Wrote {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
