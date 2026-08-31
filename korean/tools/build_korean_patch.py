#!/usr/bin/env python3
"""Build a directly installable Wizardry VI Korean localization package."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
import zipfile
from pathlib import Path

from PIL import ImageFont


WROOT_SHA256 = "6ae1642e31e0b0a7965271dada8cb1eec82626bb907600d208dbeb728f26eba0"
EGA_SHA256 = "dd9bbaafc4a435e7380ead38c65f33e6976a6dd44703a942b937f1e9a9bdee9b"
WFONT0_SHA256 = "39261a19f201d54ac1d4f44f5b19070169052325e000ef90bd6e0d724db5e669"
WBASE_SHA256 = "78cca479006085171e4f62d7a183a0d1915f108d4a600586638a20921107f897"
SCENARIO_SHA256 = "6e5a87ca30864406f7422b3685b4f31df6683b2b6fae93b7e29d59a9a8da32dd"
TITLEPAG_SHA256 = "3a7be3d1af6bc34c970c13f762cc57c66567e019e7023633d61f1febe8342ccc"
WROOT_SIZE = 67_134
EGA_SIZE = 8_802
ASCII_FONT_SIZE = 1_024
GLYPH_BYTES = 8
RUNTIME_GLYPH_LIMIT = 1_024
ITEM_TABLE_OFFSET = 0x0380
ITEM_RECORD_SIZE = 74
ITEM_SLOT_COUNT = 483


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expect_hash(data: bytes, expected: str, label: str) -> None:
    actual = sha256(data)
    if actual != expected:
        raise ValueError(f"{label} SHA256 mismatch: expected {expected}, got {actual}")


def guarded_patch(data: bytearray, offset: int, expected: bytes, replacement: bytes, label: str) -> None:
    if len(expected) != len(replacement):
        raise ValueError(f"{label}: fixed-size patch length mismatch")
    actual = bytes(data[offset : offset + len(expected)])
    if actual != expected:
        raise ValueError(
            f"{label}: expected {expected.hex(' ')} at 0x{offset:X}, got {actual.hex(' ')}"
        )
    data[offset : offset + len(replacement)] = replacement


def load_codebook(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("encoding") != "w6-highbit-pair-v1":
        raise ValueError("unexpected codebook encoding")
    characters = payload.get("characters")
    if not isinstance(characters, list) or not all(isinstance(ch, str) and len(ch) == 1 for ch in characters):
        raise ValueError("invalid codebook characters")
    if len(characters) > RUNTIME_GLYPH_LIMIT:
        raise ValueError(f"custom glyph count {len(characters)} exceeds {RUNTIME_GLYPH_LIMIT}")
    return characters


def encode_compact_text(text: str, characters: list[str]) -> bytes:
    index_by_character = {ch: index for index, ch in enumerate(characters)}
    output = bytearray()
    for ch in text:
        if ord(ch) < 0x80:
            output.append(ord(ch))
            continue
        try:
            index = index_by_character[ch]
        except KeyError as exc:
            raise ValueError(f"SCENARIO character {ch!r} is absent from codebook") from exc
        output.extend((0x80 + index // 128, 0x80 + index % 128))
    return bytes(output)


def patch_scenario_items(
    original: bytes, translation_csv: Path, characters: list[str]
) -> tuple[bytes, dict[str, object]]:
    expect_hash(original, SCENARIO_SHA256, "SCENARIO.DBS")
    with translation_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {"category", "record_index", "variant", "translation"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError("scenario translation CSV has an invalid schema")
    patched = bytearray(original)
    seen: set[int] = set()
    max_encoded = 0
    for row in rows:
        if row["category"] != "item" or row["variant"] != "name":
            raise ValueError(f"unsupported SCENARIO field: {row}")
        index = int(row["record_index"])
        if not 0 <= index < ITEM_SLOT_COUNT or index in seen:
            raise ValueError(f"invalid or duplicate item record index: {index}")
        seen.add(index)
        encoded = encode_compact_text(row["translation"], characters)
        if not encoded or len(encoded) >= 16 or b"\0" in encoded:
            raise ValueError(
                f"item {index} encoded length must be 1..15 bytes, got {len(encoded)}"
            )
        offset = ITEM_TABLE_OFFSET + index * ITEM_RECORD_SIZE
        original_name = original[offset : offset + 16].split(b"\0", 1)[0]
        if not original_name or any(byte >= 0x80 for byte in original_name):
            raise ValueError(f"item {index} source field is not a retail ASCII name")
        patched[offset : offset + 16] = encoded + bytes(16 - len(encoded))
        max_encoded = max(max_encoded, len(encoded))
    return bytes(patched), {
        "translated_item_names": len(rows),
        "max_encoded_name_bytes": max_encoded,
        "field_capacity_bytes": 16,
        "source_sha256": sha256(original),
    }


def parse_bdf(path: Path, wanted: set[int]) -> dict[int, bytes]:
    result: dict[int, bytes] = {}
    encoding: int | None = None
    rows: list[int] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ENCODING "):
            encoding = int(line.split()[1])
        elif line == "BITMAP":
            rows = []
        elif line == "ENDCHAR":
            if encoding in wanted and rows is not None:
                if len(rows) > 8:
                    raise ValueError(f"BDF U+{encoding:04X} is taller than 8 pixels")
                result[encoding] = bytes(rows + [0] * (8 - len(rows)))
            encoding = None
            rows = None
        elif rows is not None:
            rows.append(int(line, 16))
    return result


def rasterize_ttf(path: Path, characters: list[str]) -> tuple[bytes, dict[str, object]]:
    font = ImageFont.truetype(str(path), size=8, layout_engine=ImageFont.Layout.BASIC)
    glyphs = bytearray()
    nonempty = 0
    max_mask_width = 0
    max_mask_height = 0
    offsets: set[tuple[int, int]] = set()

    for ch in characters:
        mask, offset = font.getmask2(ch, mode="1")
        width, height = mask.size
        max_mask_width = max(max_mask_width, width)
        max_mask_height = max(max_mask_height, height)
        offsets.add((int(offset[0]), int(offset[1])))
        rows = [0] * 8
        for y in range(height):
            for x in range(width):
                if not mask.getpixel((x, y)):
                    continue
                target_x = x + int(offset[0])
                target_y = y + int(offset[1]) - 1
                if not (0 <= target_x < 8 and 0 <= target_y < 8):
                    raise ValueError(
                        f"TTF glyph {ch!r} U+{ord(ch):04X} exceeds 8x8 cell at ({target_x},{target_y})"
                    )
                rows[target_y] |= 0x80 >> target_x
        if any(rows):
            nonempty += 1
        else:
            raise ValueError(f"TTF glyph {ch!r} U+{ord(ch):04X} rendered empty")
        glyphs.extend(rows)

    return bytes(glyphs), {
        "font_family": font.getname()[0],
        "font_style": font.getname()[1],
        "pixel_size": 8,
        "render_mode": "1bpp/no-antialias",
        "nonempty_glyphs": nonempty,
        "max_mask_width": max_mask_width,
        "max_mask_height": max_mask_height,
        "mask_offsets": [list(item) for item in sorted(offsets)],
    }


def build_font(original: bytes, glyph_table: bytes) -> bytes:
    if len(original) != ASCII_FONT_SIZE:
        raise ValueError(f"WFONT0 original size is {len(original)}, expected {ASCII_FONT_SIZE}")
    return original + glyph_table


def make_wroot(original: bytes, font_size: int, driver_size: int) -> tuple[bytes, dict[str, object]]:
    if len(original) != WROOT_SIZE:
        raise ValueError("unexpected WROOT size")
    if font_size > 0xFFFF:
        raise ValueError("extended WFONT0 exceeds 16-bit loader size")
    patched = bytearray(original)
    font_allocation_size = (font_size + 15) & ~15

    # The display driver is loaded at segment offset 0x100. Keep its resident
    # allocation large enough for the appended custom glyph table.
    driver_allocation_bytes = ((driver_size + 0x100 + 15) // 16) * 16
    driver_paragraphs = driver_allocation_bytes // 16
    guarded_patch(
        patched,
        0x1D82,
        bytes.fromhex("40 02"),
        struct.pack("<H", driver_paragraphs),
        "display-driver allocation paragraphs",
    )
    guarded_patch(
        patched,
        0x215A,
        bytes.fromhex("B9 00 24"),
        b"\xB9" + struct.pack("<H", driver_size),
        "display-driver read size",
    )

    # Resident allocation: AX=font_size, then the retail code divides by 16.
    guarded_patch(
        patched,
        0x2297,
        bytes.fromhex("B8 00 04"),
        b"\xB8" + struct.pack("<H", font_allocation_size),
        "WFONT0 allocation size",
    )
    # Fixed-size WFONT0 DOS read.
    guarded_patch(
        patched,
        0x23C7,
        bytes.fromhex("B9 00 04"),
        b"\xB9" + struct.pack("<H", font_size),
        "WFONT0 read size",
    )

    # Persist the custom index high bits from character argument AH in the
    # otherwise-unused low nibble of the cell style byte. ROR AX,4 forms the
    # retail style high nibble in AH without consuming CL.
    cell_pack_original = bytes.fromhex("8B 46 08 8A E0 B1 04 D2 E4 8A 46 06")
    cell_pack_custom = bytes.fromhex("8B 46 08 C1 C8 04 0A 66 07 8A 46 06")
    guarded_patch(patched, 0x250E, cell_pack_original, cell_pack_custom, "custom cell pack")

    # Complete 52-byte rewrite of the WFONT0 NUL-string function. DI is the
    # source pointer because the draw-character routine preserves DI but not BX.
    pair_loop_original = bytes(patched[0x26E9:0x271D])
    if not pair_loop_original.startswith(bytes.fromhex("55 8B EC 83 EC 04 56 06 1E")):
        raise ValueError("WFONT0 string-loop prologue signature mismatch")
    if bytes(patched[0x26FB:0x2707]) != bytes.fromhex("8B 5E FE FF 46 FE 8A 07 32 E4 0A C0"):
        raise ValueError("WFONT0 one-byte loop signature mismatch")
    pair_loop = bytes.fromhex(
        "55 8B EC 56 57 06 1E 8B 76 04 8B 7E 06 "
        "8A 05 47 32 E4 0A C0 74 18 A8 80 74 07 "
        "2C 80 8A E0 8A 05 47 FF 76 08 50 56 E8 A5 FD "
        "83 C4 06 EB DF 1F 07 5F 5E 5D C3"
    )
    if len(pair_loop) != 0x34:
        raise AssertionError(f"pair loop is {len(pair_loop)} bytes, expected 52")
    patched[0x26E9:0x271D] = pair_loop

    # WFONT1..4 strings are used by the master-options menu. Keep retail ASCII
    # on entry1, and pack custom cells as:
    #   AH high nibble = original WFONT1..4 ID
    #   AH bit 3       = custom-menu sentinel
    #   AH bits 0..2  = codebook index bits 7..9
    #   AL bits 0..6  = codebook index bits 0..6 (AL remains high-bit set)
    # This preserves the menu font identity across refreshes instead of
    # converting menu text into a WFONT0 cell with a black background.
    pair_loop_entry1_original = bytes(patched[0x271D:0x2756])
    if not pair_loop_entry1_original.startswith(bytes.fromhex("55 8B EC 83 EC 04 56 06 1E")):
        raise ValueError("WFONT1..4 string-loop prologue signature mismatch")
    loop2_cs = 0x251D
    loop2 = bytearray(bytes.fromhex("55 8B EC 56 57 8B 7E 04 8B 76 06"))
    loop2_body = len(loop2)
    loop2 += bytes.fromhex("AC 0A C0 74 00 A8 80 75 00")
    done_disp = loop2_body + 4
    custom_disp = loop2_body + 8
    loop2 += bytes.fromhex("FF 76 08 50 57 E8 00 00 EB 00")
    ascii_call = len(loop2) - 5
    ascii_cleanup_disp = len(loop2) - 1
    custom_label = len(loop2)
    loop2 += bytes.fromhex("8B 5E 08 C0 E3 04 2C 78 0A D8 AC 53 50 57 E8 00 00")
    custom_call = len(loop2) - 3
    cleanup_label = len(loop2)
    loop2 += bytes.fromhex("83 C4 06 EB 00")
    loop_back_disp = len(loop2) - 1
    done_label = len(loop2)
    loop2 += bytes.fromhex("5F 5E 5D C3")
    if len(loop2) > len(pair_loop_entry1_original):
        raise AssertionError("pair-aware WFONT1..4 loop does not fit retail function")
    loop2 += b"\x90" * (len(pair_loop_entry1_original) - len(loop2))
    loop2[done_disp] = (done_label - (done_disp + 1)) & 0xFF
    loop2[custom_disp] = (custom_label - (custom_disp + 1)) & 0xFF
    loop2[ascii_cleanup_disp] = (cleanup_label - (ascii_cleanup_disp + 1)) & 0xFF
    loop2[loop_back_disp] = (loop2_body - (loop_back_disp + 1)) & 0xFF
    ascii_call_next_cs = loop2_cs + ascii_call + 3
    custom_call_next_cs = loop2_cs + custom_call + 3
    struct.pack_into("<h", loop2, ascii_call + 1, 0x23E3 - ascii_call_next_cs)
    struct.pack_into("<h", loop2, custom_call + 1, 0x23E3 - custom_call_next_cs)
    patched[0x271D:0x2756] = loop2

    # refreshwindow: a high-bit custom cell with AH bit 3 set belongs to the
    # WFONT1..4 menu renderer. Other high-bit cells remain WFONT0 narrative
    # text. Retail ASCII still dispatches from font ID 0..4 exactly as before.
    refresh_original = bytes(patched[0x2E31:0x2E4C])
    refresh = bytes.fromhex(
        "8B 07 A8 80 74 07 F6 C4 08 75 20 EB 28 "
        "F6 C4 0F 74 23 80 FC 04 76 14 EB 02 90 90"
    )
    guarded_patch(patched, 0x2E31, refresh_original, refresh, "refresh split custom dispatch")

    # Static target checks, including the historically error-prone near call.
    call_site_cs = 0x24E9 + 38
    displacement = struct.unpack_from("<h", pair_loop, 39)[0]
    pair_call_target = call_site_cs + 3 + displacement
    if pair_call_target != 0x22B7:
        raise AssertionError(f"pair-loop call target is 0x{pair_call_target:X}, expected 0x22B7")
    if patched[0x2E69:0x2E6E] != bytes.fromhex("2E FF 1E 8A 1B"):
        raise AssertionError("refresh entry0 far-call target signature changed")

    return bytes(patched), {
        "allocation_bytes": font_allocation_size,
        "allocation_paragraphs": font_allocation_size // 16,
        "read_bytes": font_size,
        "driver_allocation_bytes": driver_allocation_bytes,
        "driver_allocation_paragraphs": driver_paragraphs,
        "driver_read_bytes": driver_size,
        "pair_loop_file": "0x26E9",
        "pair_loop_cs": "0x24E9",
        "pair_draw_call_target_cs": f"0x{pair_call_target:04X}",
        "pair_entry1_loop_file": "0x271D",
        "pair_entry1_loop_cs": "0x251D",
        "draw_character_target_cs": "0x22B7",
        "menu_draw_character_target_cs": "0x23E3",
        "menu_custom_cell_sentinel": "AH bit 3",
        "refresh_entry0_far_pointer_cs": "0x1B8A",
        "overlay_zero_window_used": False,
    }


def make_ega(original: bytes, glyph_table: bytes) -> tuple[bytes, dict[str, object]]:
    if len(original) != EGA_SIZE:
        raise ValueError("unexpected EGA.DRV size")
    patched = bytearray(original)
    wfont0_helper_file = len(patched)
    wfont0_helper_com = wfont0_helper_file + 0x100

    # Keep the retail four-plane WFONT0 renderer intact.  The replacement only
    # decodes our packed lead/trail pair and supplies the corresponding glyph
    # pointer in the stack frame.  Consequently foreground, background,
    # inversion, dialog boxes and panel borders all retain the game's original
    # per-call semantics instead of being guessed from framebuffer pixels.
    wfont0_helper = bytearray(bytes.fromhex("50 8A D8 32 FF F6 C3 80 75 11"))
    wfont0_helper += bytes.fromhex(
        "B1 03 D3 E3 2E 8B 16 55 01 89 56 FE 89 5E FC 58 C3"
    )
    wfont0_helper += bytes.fromhex(
        "81 E3 7F 00 8A D4 32 F6 80 E2 0F B1 07 D3 E2 0B DA "
        "B1 03 D3 E3 81 C3 00 00 8C CA 89 56 FE 89 5E FC 58 C3"
    )

    # WFONT1..4 custom cells retain the retail menu font ID. Build one temporary
    # 32-byte four-plane glyph in the driver segment, then rejoin the untouched
    # retail WFONT1 renderer at COM 0x0570. That renderer already handles both
    # direct VRAM output and its off-screen backing-buffer branch.
    menu_helper_file = wfont0_helper_file + len(wfont0_helper)
    menu_helper_com = menu_helper_file + 0x100
    menu_helper = bytearray()
    menu_labels: dict[str, int] = {}
    menu_rel8: list[tuple[int, str]] = []

    def menu_mark(label: str) -> None:
        if label in menu_labels:
            raise AssertionError(f"duplicate menu helper label: {label}")
        menu_labels[label] = len(menu_helper)

    def menu_emit(hex_bytes: str) -> None:
        menu_helper.extend(bytes.fromhex(hex_bytes))

    def menu_jump(opcode: int, label: str) -> None:
        menu_helper.extend((opcode, 0))
        menu_rel8.append((len(menu_helper) - 1, label))

    menu_emit("50 A8 80")                         # push ax; test al,80h
    menu_jump(0x75, "custom")                    # jnz custom
    menu_emit("8A D8 32 FF B1 05 D3 E3 8B F3")  # retail ASCII index * 32
    menu_emit("2E 8B 16 59 01 FE CC")
    menu_jump(0x74, "font_selected")
    menu_emit("2E 8B 16 5D 01 FE CC")
    menu_jump(0x74, "font_selected")
    menu_emit("2E 8B 16 61 01 FE CC")
    menu_jump(0x74, "font_selected")
    menu_emit("2E 8B 16 65 01")
    menu_mark("font_selected")
    menu_emit("8E DA 58 C3")                    # mov ds,dx; pop ax; ret

    menu_mark("custom")
    menu_emit(
        "8A D8 32 FF 81 E3 7F 00 "              # BX = trail low 7 bits
        "8A D4 80 E2 07 32 F6 B1 07 D3 E2 0B DA "
        "B1 03 D3 E3 81 C3 00 00 8B F3 "        # SI = table + index*8
        "8A D4 B1 04 D2 EA 80 E2 0F "           # DL = preserved font ID
        "0E 1F 0E 07 57 BF 00 00"               # DS=ES=CS; save screen DI
    )
    menu_emit("80 FA 02")
    menu_jump(0x74, "plane0_zero")
    menu_emit("56 B9 08 00 F3 A4 5E")
    menu_jump(0xEB, "plane0_done")
    menu_mark("plane0_zero")
    menu_emit("32 C0 B9 08 00 F3 AA")
    menu_mark("plane0_done")

    menu_emit("80 FA 03")
    menu_jump(0x74, "plane1_zero")
    menu_emit("56 B9 08 00 F3 A4 5E")
    menu_jump(0xEB, "plane1_done")
    menu_mark("plane1_zero")
    menu_emit("32 C0 B9 08 00 F3 AA")
    menu_mark("plane1_done")

    menu_emit("80 FA 02")
    menu_jump(0x75, "plane2_zero")
    menu_emit("56 B9 08 00 F3 A4 5E")
    menu_jump(0xEB, "plane2_done")
    menu_mark("plane2_zero")
    menu_emit("32 C0 B9 08 00 F3 AA")
    menu_mark("plane2_done")

    menu_emit("B0 FF B9 08 00 F3 AA 5F BE 00 00 58 C3")

    for disp_at, label in menu_rel8:
        if label not in menu_labels:
            raise AssertionError(f"missing menu helper label: {label}")
        displacement = menu_labels[label] - (disp_at + 1)
        if not -128 <= displacement <= 127:
            raise ValueError(f"menu helper short jump to {label} is out of range")
        menu_helper[disp_at] = displacement & 0xFF

    menu_buffer_file = menu_helper_file + len(menu_helper)
    menu_buffer_com = menu_buffer_file + 0x100
    table_file_offset = menu_buffer_file + 32
    table_com = table_file_offset + 0x100
    table_imm = bytes.fromhex("81 C3 00 00")
    table_add0 = wfont0_helper.find(table_imm)
    table_add1 = menu_helper.find(table_imm)
    if table_add0 < 0 or table_add1 < 0:
        raise AssertionError("EGA custom table relocation marker missing")
    struct.pack_into("<H", wfont0_helper, table_add0 + 2, table_com)
    struct.pack_into("<H", menu_helper, table_add1 + 2, table_com)
    menu_buffer_load = menu_helper.find(bytes.fromhex("BF 00 00"))
    menu_buffer_reload = menu_helper.find(bytes.fromhex("BE 00 00"))
    if menu_buffer_load < 0 or menu_buffer_reload < 0:
        raise AssertionError("EGA menu buffer relocation marker missing")
    struct.pack_into("<H", menu_helper, menu_buffer_load + 1, menu_buffer_com)
    struct.pack_into("<H", menu_helper, menu_buffer_reload + 1, menu_buffer_com)

    entry0_call_com = 0x02A7
    entry0_call_next = entry0_call_com + 3
    displacement = wfont0_helper_com - entry0_call_next
    if not -0x8000 <= displacement <= 0x7FFF:
        raise ValueError("EGA WFONT0 helper is outside near-call range")
    entry_patch = b"\xE8" + struct.pack("<h", displacement) + b"\x90" * 16
    guarded_patch(
        patched,
        0x1A7,
        bytes.fromhex("8A D8 32 FF B1 03 D3 E3 2E 8B 16 55 01 89 56 FE 89 5E FC"),
        entry_patch,
        "EGA WFONT0 index decoder",
    )
    entry1_call_com = 0x0544
    entry1_call_next = entry1_call_com + 3
    entry1_displacement = menu_helper_com - entry1_call_next
    if not -0x8000 <= entry1_displacement <= 0x7FFF:
        raise ValueError("EGA WFONT1 helper is outside near-call range")
    entry1_patch = b"\xE8" + struct.pack("<h", entry1_displacement) + b"\x90" * 41
    guarded_patch(
        patched,
        0x444,
        bytes.fromhex(
            "8A D8 32 FF B1 05 D3 E3 8B F3 2E 8B 16 59 01 FE CC 74 17 "
            "2E 8B 16 5D 01 FE CC 74 0E 2E 8B 16 61 01 FE CC 74 05 "
            "2E 8B 16 65 01 8E DA"
        ),
        entry1_patch,
        "EGA WFONT1..4 index decoder",
    )
    patched.extend(bytes(wfont0_helper))
    patched.extend(bytes(menu_helper))
    patched.extend(b"\x00" * 32)
    patched.extend(glyph_table)
    if len(patched) + 0x100 > 0xFFFF:
        raise ValueError("patched EGA exceeds its 16-bit resident segment")

    encoded_disp = struct.unpack_from("<h", patched, 0x1A8)[0]
    actual_target = entry0_call_next + encoded_disp
    if actual_target != wfont0_helper_com:
        raise AssertionError("EGA WFONT0 near-call target verification failed")
    encoded_entry1_disp = struct.unpack_from("<h", patched, 0x445)[0]
    actual_entry1_target = entry1_call_next + encoded_entry1_disp
    if actual_entry1_target != menu_helper_com:
        raise AssertionError("EGA WFONT1 near-call target verification failed")
    if patched[table_file_offset : table_file_offset + len(glyph_table)] != glyph_table:
        raise AssertionError("embedded EGA glyph table changed")

    return bytes(patched), {
        "original_bytes": len(original),
        "patched_bytes": len(patched),
        "driver_read_bytes_required": len(patched),
        "custom_helper_file": f"0x{wfont0_helper_file:04X}",
        "custom_helper_com": f"0x{wfont0_helper_com:04X}",
        "menu_helper_file": f"0x{menu_helper_file:04X}",
        "menu_helper_com": f"0x{menu_helper_com:04X}",
        "menu_buffer_file": f"0x{menu_buffer_file:04X}",
        "menu_buffer_com": f"0x{menu_buffer_com:04X}",
        "custom_table_file": f"0x{table_file_offset:04X}",
        "custom_table_com": f"0x{table_com:04X}",
        "custom_table_bytes": len(glyph_table),
        "wfont0_background_mode": "retail four-plane renderer; custom patch changes glyph address only",
        "entry0_call_com": f"0x{entry0_call_com:04X}",
        "entry0_call_target_com": f"0x{actual_target:04X}",
        "entry1_call_com": f"0x{entry1_call_com:04X}",
        "entry1_call_target_com": f"0x{actual_entry1_target:04X}",
        "ascii_wfont0_segment_pointer_cs": "0x0155",
        "custom_glyph_segment": "CS",
        "menu_background_color": 8,
        "menu_font_colors": {"1": 3, "2": 14, "3": 1, "4": 3},
    }


def make_wbase(original: bytes) -> tuple[bytes, dict[str, object]]:
    """Keep full Korean gender/race/class strings in the compact roster."""
    if len(original) != 14930:
        raise ValueError("unexpected WBASE.OVR size")
    patched = bytearray(original)

    def rewrite_gender(offset: int, style: int, string_call_offset: int, label: str) -> None:
        old = bytes(patched[offset : offset + 19])
        if old[:4] != bytes([0xB8, style, 0x00, 0x50]) or old[4:9] != bytes.fromhex("8A 46 EC 2A E4"):
            raise ValueError(f"{label} signature mismatch")
        old_call_disp = struct.unpack_from("<h", patched, string_call_offset + 1)[0]
        target = string_call_offset + 3 + old_call_disp
        replacement = bytearray(bytes([0xB8, style, 0x00, 0x50]))
        replacement += bytes.fromhex("8D 46 EC 50 FF 76 04 E8 00 00 83 C4 06 90 90")
        call_at = offset + 11
        struct.pack_into("<h", replacement, 12, target - (call_at + 3))
        guarded_patch(patched, offset, old, bytes(replacement), label)

    # Retail prints only the first byte of MALE/FEMALE and forcibly terminates
    # race/class names after three bytes. A Korean glyph is a two-byte pair, so
    # those byte-oriented abbreviations cut strings in half. Draw the complete
    # messages instead; the roster has enough horizontal room for them.
    rewrite_gender(0x1FB4, 7, 0x2002, "roster gender string mode 1")
    rewrite_gender(0x209D, 3, 0x20EB, "roster gender string mode 2")
    for offset, label in (
        (0x1FF3, "roster race truncation mode 1"),
        (0x2034, "roster class truncation mode 1"),
        (0x20DC, "roster race truncation mode 2"),
        (0x2112, "roster class truncation mode 2"),
    ):
        guarded_patch(
            patched,
            offset,
            bytes.fromhex("C6 46 EF 00"),
            bytes.fromhex("90 90 90 90"),
            label,
        )

    return bytes(patched), {
        "full_gender_strings": True,
        "race_three_byte_truncation_removed": True,
        "class_three_byte_truncation_removed": True,
    }


def validate_bdf_equivalence(bdf: Path, characters: list[str], glyph_table: bytes) -> dict[str, object]:
    expected = parse_bdf(bdf, {ord(ch) for ch in characters})
    missing = [ch for ch in characters if ord(ch) not in expected]
    mismatches: list[str] = []
    for index, ch in enumerate(characters):
        actual = glyph_table[index * 8 : index * 8 + 8]
        if ord(ch) in expected and actual != expected[ord(ch)]:
            mismatches.append(f"{ch} U+{ord(ch):04X}")
    if missing or mismatches:
        raise ValueError(
            f"TTF/BDF pixel validation failed: missing={missing[:8]}, mismatches={mismatches[:8]}"
        )
    return {
        "reference": str(bdf),
        "checked_glyphs": len(characters),
        "missing_glyphs": len(missing),
        "pixel_mismatches": len(mismatches),
    }


def verify_runtime_contract(glyph_count: int) -> dict[str, object]:
    if glyph_count > 1024:
        raise AssertionError("menu custom-cell sentinel leaves room for at most 1,024 glyphs")
    checked = 0
    menu_checked = 0
    for index in range(glyph_count):
        lead = 0x80 + index // 128
        trail = 0x80 + index % 128
        pair_word = ((lead - 0x80) << 8) | trail
        for style in range(16):
            cell = (style << 12) | pair_word
            if not cell & 0x80:
                raise AssertionError("custom cell flag was lost")
            restored_index = ((cell >> 8) & 0x0F) << 7 | (cell & 0x7F)
            restored_style = (cell >> 12) & 0x0F
            glyph_offset = (128 + restored_index) * GLYPH_BYTES
            if restored_index != index:
                raise AssertionError("custom index did not survive the persistent cell")
            if restored_style != style:
                raise AssertionError("style did not survive the persistent cell")
            if glyph_offset != ASCII_FONT_SIZE + index * GLYPH_BYTES:
                raise AssertionError("EGA glyph address contract mismatch")
            checked += 1
        for font_id in range(1, 5):
            menu_cell = (font_id << 12) | (0x08 << 8) | pair_word
            if not menu_cell & 0x80 or not menu_cell & 0x0800:
                raise AssertionError("custom menu cell flags were lost")
            restored_index = ((menu_cell >> 8) & 0x07) << 7 | (menu_cell & 0x7F)
            restored_font = (menu_cell >> 12) & 0x0F
            if restored_index != index or restored_font != font_id:
                raise AssertionError("menu custom index/font did not survive the persistent cell")
            menu_checked += 1
    return {
        "indices_checked": glyph_count,
        "styles_per_index": 16,
        "index_style_cases": checked,
        "menu_font_cases": menu_checked,
        "menu_custom_sentinel_bit": 3,
        "max_index": glyph_count - 1,
        "first_custom_offset": ASCII_FONT_SIZE,
        "last_custom_offset": ASCII_FONT_SIZE + (glyph_count - 1) * GLYPH_BYTES,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-dir", type=Path, required=True)
    parser.add_argument("--msg-build", type=Path, required=True)
    parser.add_argument("--ttf", type=Path, required=True)
    parser.add_argument("--bdf", type=Path, required=True)
    parser.add_argument("--titlepag", type=Path, required=True)
    parser.add_argument("--scenario-translations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--zip", dest="zip_path", type=Path, required=True)
    args = parser.parse_args()

    characters = load_codebook(args.msg_build / "codebook.json")
    build_report = json.loads((args.msg_build / "build_report.json").read_text(encoding="utf-8"))
    if build_report.get("source_row_count") != 5161:
        raise ValueError("MSG build did not validate all 5,161 messages")
    if build_report.get("record_start_bank_crossings") != 0:
        raise ValueError("MSG build contains a range bank crossing")
    if build_report.get("max_encoded_bytes", 256) > 255:
        raise ValueError("MSG build contains an oversized decoded fragment")
    if build_report.get("custom_glyph_count") != len(characters):
        raise ValueError("MSG report/codebook custom glyph count mismatch")

    wroot_original = (args.game_dir / "WROOT.EXE").read_bytes()
    ega_original = (args.game_dir / "EGA.DRV").read_bytes()
    font_original = (args.game_dir / "WFONT0.EGA").read_bytes()
    wbase_original = (args.game_dir / "WBASE.OVR").read_bytes()
    scenario_original = (args.game_dir / "SCENARIO.DBS").read_bytes()
    titlepag = args.titlepag.read_bytes()
    expect_hash(wroot_original, WROOT_SHA256, "WROOT.EXE")
    expect_hash(ega_original, EGA_SHA256, "EGA.DRV")
    expect_hash(font_original, WFONT0_SHA256, "WFONT0.EGA")
    expect_hash(wbase_original, WBASE_SHA256, "WBASE.OVR")
    expect_hash(scenario_original, SCENARIO_SHA256, "SCENARIO.DBS")
    expect_hash(titlepag, TITLEPAG_SHA256, "TITLEPAG.EGA")
    if len(titlepag) != 32768:
        raise ValueError("unexpected TITLEPAG.EGA size")

    glyph_table, raster_report = rasterize_ttf(args.ttf, characters)
    bdf_report = validate_bdf_equivalence(args.bdf, characters, glyph_table)
    runtime_contract = verify_runtime_contract(len(characters))
    font_patched = build_font(font_original, glyph_table)
    expected_font_size = ASCII_FONT_SIZE + len(characters) * GLYPH_BYTES
    if len(font_patched) != expected_font_size:
        raise AssertionError("extended WFONT0 size mismatch")
    if font_patched[:ASCII_FONT_SIZE] != font_original:
        raise AssertionError("original WFONT0 ASCII region changed")

    ega_patched, ega_report = make_ega(ega_original, glyph_table)
    wroot_patched, wroot_report = make_wroot(wroot_original, len(font_patched), len(ega_patched))
    wbase_patched, wbase_report = make_wbase(wbase_original)
    scenario_patched, scenario_report = patch_scenario_items(
        scenario_original, args.scenario_translations, characters
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "WROOT.EXE": wroot_patched,
        "EGA.DRV": ega_patched,
        "WFONT0.EGA": font_patched,
        "MSG.DBS": (args.msg_build / "MSG.DBS").read_bytes(),
        "MSG.HDR": (args.msg_build / "MSG.HDR").read_bytes(),
        "MISC.HDR": (args.msg_build / "MISC.HDR").read_bytes(),
        "TITLEPAG.EGA": titlepag,
        "WBASE.OVR": wbase_patched,
        "SCENARIO.DBS": scenario_patched,
    }
    for name, data in outputs.items():
        (args.output_dir / name).write_bytes(data)

    readme = (
        "Wizardry VI Korean localization v0.1.0-alpha.1\n\n"
        "1. Back up the original Wizardry VI game folder.\n"
        "2. Extract every file in this ZIP directly into the game folder and overwrite.\n"
        "3. Start the game normally. No script or font installation is required.\n"
        "4. Existing save files are not included or overwritten by this ZIP.\n\n"
        "Includes Korean messages, compact menus, 452 item names, and the Korean intro logo.\n"
    )
    (args.output_dir / "README_TEST.txt").write_text(readme, encoding="utf-8", newline="\r\n")
    font_license = Path(__file__).resolve().parents[1] / "fonts" / "OFL.txt"
    if not font_license.is_file():
        raise FileNotFoundError(f"font license not found: {font_license}")
    shutil.copy2(font_license, args.output_dir / "Galmuri7-OFL.txt")

    report = {
        "passed": True,
        "source": {
            "WROOT.EXE": {"bytes": len(wroot_original), "sha256": sha256(wroot_original)},
            "EGA.DRV": {"bytes": len(ega_original), "sha256": sha256(ega_original)},
            "WFONT0.EGA": {"bytes": len(font_original), "sha256": sha256(font_original)},
        },
        "messages": {
            "decoded_message_count": build_report["source_row_count"],
            "translated_row_count": build_report["translated_row_count"],
            "changed_message_count": build_report["changed_message_count"],
            "banks": build_report["msg_dbs_banks"],
            "range_bank_crossings": build_report["record_start_bank_crossings"],
            "max_encoded_bytes": build_report["max_encoded_bytes"],
        },
        "font": {
            "custom_glyph_count": len(characters),
            "runtime_limit": RUNTIME_GLYPH_LIMIT,
            "original_ascii_bytes_unchanged": True,
            "glyph_table_bytes": len(glyph_table),
            "output_bytes": len(font_patched),
            "expected_output_bytes": expected_font_size,
            "ttf_sha256": sha256(args.ttf.read_bytes()),
            **raster_report,
            "bdf_equivalence": bdf_report,
        },
        "wroot": wroot_report,
        "wbase": wbase_report,
        "scenario": scenario_report,
        "ega": ega_report,
        "runtime_contract": runtime_contract,
        "outputs": {name: {"bytes": len(data), "sha256": sha256(data)} for name, data in outputs.items()},
    }
    report_path = args.output_dir / "STATIC_VERIFICATION.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")

    args.zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in ["WROOT.EXE", "EGA.DRV", "WFONT0.EGA", "WBASE.OVR", "SCENARIO.DBS", "MSG.DBS", "MSG.HDR", "MISC.HDR", "TITLEPAG.EGA", "README_TEST.txt", "Galmuri7-OFL.txt"]:
            archive.write(args.output_dir / name, arcname=name)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"ZIP: {args.zip_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
