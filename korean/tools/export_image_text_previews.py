#!/usr/bin/env python3
"""Export local previews for Wizardry VI image-text auditing.

Supported targets:
- 32768-byte full-screen EGA files (`TITLEPAG`, `GRAVEYRD`, `DRAGONSC`)
- `CREDITS.PIC` sparse RLE sprite frames

The previews are local QA artifacts.  Do not commit generated PNGs or original
commercial assets to the repository.
"""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover - environment-dependent
    raise SystemExit("Pillow is required: python -m pip install pillow") from exc

TITLEPAG_PALETTE = [
    (0, 0, 0),
    (255, 255, 255),
    (85, 85, 255),
    (255, 85, 255),
    (255, 85, 85),
    (255, 255, 85),
    (85, 255, 85),
    (85, 255, 255),
    (85, 85, 85),
    (170, 170, 170),
    (0, 0, 170),
    (170, 0, 170),
    (170, 0, 0),
    (170, 85, 0),
    (0, 170, 0),
    (0, 170, 170),
]


def decode_fullscreen_ega(data: bytes) -> Image.Image:
    if len(data) != 32768:
        raise ValueError(f"expected 32768-byte full-screen EGA file, got {len(data)}")

    width, height = 320, 200
    bytes_per_row = width // 8
    pixels = [0] * (width * height)

    # Each of four 8192-byte slots contains 8000 bytes of plane data followed
    # by 192 bytes of padding.  This is sequential planar, not row-interleaved.
    for plane in range(4):
        plane_base = plane * 8192
        for y in range(height):
            row_base = plane_base + y * bytes_per_row
            for byte_idx in range(bytes_per_row):
                value = data[row_base + byte_idx]
                for bit in range(8):
                    if value & (0x80 >> bit):
                        x = byte_idx * 8 + bit
                        pixels[y * width + x] |= 1 << plane

    image = Image.new("RGB", (width, height))
    image.putdata([TITLEPAG_PALETTE[p] for p in pixels])
    return image


def decode_rle(data: bytes) -> bytes:
    chunk_size = 0x1000
    output = bytearray()
    done = False
    offset = 0
    while not done and offset < len(data):
        chunk = data[offset : offset + chunk_size]
        offset += chunk_size
        i = 0
        while i < 0x0FFF and i < len(chunk):
            ctrl = chunk[i]
            i += 1
            if ctrl == 0:
                done = True
                break
            if ctrl < 0x80:
                output.extend(chunk[i : i + ctrl])
                i += ctrl
            elif i < len(chunk):
                value = chunk[i]
                i += 1
                output.extend([value] * (256 - ctrl))
    return bytes(output)


def decode_credits_frames(data: bytes) -> list[tuple[int, Image.Image]]:
    decompressed = decode_rle(data)
    if len(decompressed) < 2:
        raise ValueError("credits PIC decompressed stream too short")
    header_size = struct.unpack_from("<H", decompressed, 0)[0]
    frames: list[tuple[int, Image.Image]] = []

    for frame_index in range(header_size // 24):
        start = frame_index * 24
        offset, wh = struct.unpack_from("<2H", decompressed, start)
        if offset == 0 and wh == 0:
            continue
        width_tiles = wh & 0xFF
        height_tiles = (wh >> 8) & 0xFF
        if not width_tiles or not height_tiles:
            continue
        mask = decompressed[start + 4 : start + 24]
        set_bits = sum(value.bit_count() for value in mask)
        payload = decompressed[offset : offset + set_bits * 32]

        full = bytearray(b"\xFF" * (width_tiles * height_tiles * 32))
        payload_pos = 0
        for tile_index in range(width_tiles * height_tiles):
            byte_pos = tile_index // 8
            bit_pos = tile_index % 8
            if byte_pos < len(mask) and mask[byte_pos] & (1 << bit_pos):
                full[tile_index * 32 : (tile_index + 1) * 32] = payload[
                    payload_pos : payload_pos + 32
                ]
                payload_pos += 32

        width, height = width_tiles * 8, height_tiles * 8
        pixels = [15] * (width * height)
        for tile_index in range(width_tiles * height_tiles):
            tx = tile_index % width_tiles
            ty = tile_index // width_tiles
            base = tile_index * 32
            for row in range(8):
                for x in range(8):
                    color = 0
                    mask_bit = 0x80 >> x
                    for plane in range(4):
                        if full[base + plane * 8 + row] & mask_bit:
                            color |= 1 << plane
                    pixels[(ty * 8 + row) * width + tx * 8 + x] = color

        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        rgba = []
        for color_index in pixels:
            if color_index == 15:
                rgba.append((0, 0, 0, 0))
            else:
                r, g, b = TITLEPAG_PALETTE[color_index]
                rgba.append((r, g, b, 255))
        image.putdata(rgba)
        frames.append((frame_index, image))

    return frames


def make_contact_sheet(frames: list[tuple[int, Image.Image]], scale: int = 2) -> Image.Image:
    if not frames:
        raise ValueError("no frames")
    cols = 4
    max_w = max(img.width for _, img in frames) * scale
    max_h = max(img.height for _, img in frames) * scale
    cell_w, cell_h = max_w + 16, max_h + 24
    rows = math.ceil(len(frames) / cols)
    sheet = Image.new("RGB", (cell_w * cols, cell_h * rows), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for index, (frame_id, image) in enumerate(frames):
        x = (index % cols) * cell_w
        y = (index // cols) * cell_h
        draw.text((x + 2, y + 2), f"frame {frame_id}", fill=(255, 255, 255))
        resized = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
        sheet.paste(resized, (x, y + 18), resized)
    return sheet


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("gamedata", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("output/image_text_audit"))
    parser.add_argument("--scale", type=int, default=2)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    names = ["TITLEPAG.EGA", "GRAVEYRD.EGA", "DRAGONSC.EGA"]
    lower_map = {p.name.lower(): p for p in args.gamedata.iterdir() if p.is_file()}
    for name in names:
        path = lower_map.get(name.lower())
        if not path:
            print(f"skip missing {name}")
            continue
        image = decode_fullscreen_ega(path.read_bytes())
        out = args.output_dir / f"{name.lower()}.png"
        image.resize(
            (image.width * args.scale, image.height * args.scale),
            Image.Resampling.NEAREST,
        ).save(out)
        print(f"wrote {out}")

    credits = lower_map.get("credits.pic")
    if credits:
        frames = decode_credits_frames(credits.read_bytes())
        contact = make_contact_sheet(frames, scale=args.scale)
        out = args.output_dir / "credits_contact.png"
        contact.save(out)
        print(f"wrote {out} ({len(frames)} frames)")
    else:
        print("skip missing CREDITS.PIC")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
