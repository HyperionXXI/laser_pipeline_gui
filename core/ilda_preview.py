"""
ILDA preview renderer for Laser Pipeline GUI.

Supports (read + preview):
- Format 0: 3D indexed color
- Format 1: 2D indexed color
- Format 4: 3D true color
- Format 5: 2D true color
- Format 2: palette blocks (used for indexed formats when present)

The GUI expects:
    from core.ilda_preview import render_ilda_preview

Coordinate system:
- ILDA coordinates are signed 16-bit [-32768..32767]
- We map them to a square PNG with margin.

Notes:
- This module is intentionally "generic": it tries to be tolerant with ILDA files
  encountered in the wild (misaligned blocks, extra bytes, missing palette blocks).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union
import os
import struct

from PIL import Image, ImageDraw


# -----------------------------
# Palettes
# -----------------------------

RGB = Tuple[int, int, int]


def _clamp_u8(x: int) -> int:
    return 0 if x < 0 else 255 if x > 255 else int(x)


def palette_idtf14() -> List[RGB]:
    """
    A pragmatic preview palette. Not a strict spec reproduction; good for sanity checks.
    Index 0 is black.
    """
    pal = [(0, 0, 0)] * 256
    base = {
        1: (255, 0, 0),       # red
        2: (0, 255, 0),       # green
        3: (0, 0, 255),       # blue
        4: (255, 255, 0),     # yellow
        5: (255, 0, 255),     # magenta
        6: (0, 255, 255),     # cyan
        7: (255, 255, 255),   # white
        8: (255, 128, 0),     # orange
        9: (128, 0, 255),     # purple
        10: (0, 128, 255),    # azure
        11: (128, 255, 0),    # lime
        12: (255, 0, 128),    # pink
        13: (0, 255, 128),    # spring green
        14: (128, 128, 128),  # gray
    }
    for i, c in base.items():
        pal[i] = c

    # Fill remaining indices with a small color cube for nicer previews
    idx = 15
    steps = [0, 51, 102, 153, 204, 255]
    for r in steps:
        for g in steps:
            for b in steps:
                if idx >= 256:
                    break
                pal[idx] = (r, g, b)
                idx += 1
        if idx >= 256:
            break
    return pal


def palette_white63() -> List[RGB]:
    """
    For files that use a single color index and where you just want it to show as white.
    We map indices 1..63 to white; other indices fall back to idtf14.
    """
    pal = palette_idtf14()
    for i in range(1, 64):
        pal[i] = (255, 255, 255)
    return pal


def get_palette_by_name(name: str) -> List[RGB]:
    n = (name or "").strip().lower()
    if n in ("idtf14", "idtf", "default"):
        return palette_idtf14()
    if n in ("white63", "white", "mono", "monochrome"):
        return palette_white63()
    raise ValueError(f"Unknown palette '{name}' (supported: idtf14, white63)")


# -----------------------------
# ILDA parsing
# -----------------------------

@dataclass(frozen=True)
class IldaHeader:
    format_code: int
    frame_name: str
    company_name: str
    num_records: int
    frame_number: int
    total_frames: int
    scanner_head: int


@dataclass
class IldaFrame:
    header: IldaHeader
    # Points are stored as tuples and depend on the frame format:
    # - fmt 0: (x,y,z,status,color_index)
    # - fmt 1: (x,y,status,color_index)
    # - fmt 4: (x,y,z,status,r,g,b)
    # - fmt 5: (x,y,status,r,g,b)
    points: List[tuple]

    # Convenience accessors (handy for debugging and REPL sanity-checks)
    @property
    def format_code(self) -> int:
        return int(self.header.format_code)

    @property
    def record_count(self) -> int:
        return int(self.header.num_records)

    @property
    def frame_number(self) -> int:
        return int(self.header.frame_number)

    @property
    def total_frames(self) -> int:
        return int(self.header.total_frames)

    @property
    def frame_name(self) -> str:
        return self.header.frame_name

    @property
    def company_name(self) -> str:
        return self.header.company_name


ILDA_MAGIC = b"ILDA"
ILDA_HEADER_SIZE = 32


def _decode_ascii(b: bytes) -> str:
    return b.decode("ascii", errors="ignore").rstrip("\x00 ").strip()


def _parse_header(block: bytes) -> IldaHeader:
    """
    Parse the 32-byte ILDA header.
    Layout (big-endian):
      0..3   : "ILDA"
      4..6   : reserved
      7      : format code
      8..15  : frame name (8)
      16..23 : company name (8)
      24..25 : number of records (u16)
      26..27 : frame number (u16)
      28..29 : total frames (u16)
      30     : scanner head (u8)
      31     : reserved
    """
    if len(block) < ILDA_HEADER_SIZE or block[:4] != ILDA_MAGIC:
        raise ValueError("Not an ILDA header")
    fmt = block[7]
    frame_name = _decode_ascii(block[8:16])
    company_name = _decode_ascii(block[16:24])
    num_records = struct.unpack(">H", block[24:26])[0]
    frame_number = struct.unpack(">H", block[26:28])[0]
    total_frames = struct.unpack(">H", block[28:30])[0]
    scanner_head = block[30]
    return IldaHeader(
        format_code=int(fmt),
        frame_name=frame_name,
        company_name=company_name,
        num_records=int(num_records),
        frame_number=int(frame_number),
        total_frames=int(total_frames),
        scanner_head=int(scanner_head),
    )
    


def _record_size(fmt: int) -> Optional[int]:
    # Only formats we render
    if fmt == 0:
        return 8   # x,y,z,status,color_index
    if fmt == 1:
        return 6   # x,y,status,color_index (2+2+1+1)
    if fmt == 4:
        return 10  # x,y,z,status,r,g,b (2+2+2+1+1+1+1)
    if fmt == 5:
        return 8   # x,y,status,r,g,b (2+2+1+1+1+1)
    if fmt == 2:
        return 3   # r,g,b
    return None


def _is_blanked(status: int) -> bool:
    # ILDA "blanking" is commonly bit 6 (0x40). Some tools may also use 0x00/0x01;
    # we keep it simple and standard.
    return (status & 0x40) != 0

def _is_last_point(status: int) -> bool:
    """Return True if ILDA 'last point' bit is set (0x80)."""
    return (status & 0x80) != 0

def _parse_records(fmt: int, data: bytes, count: int) -> List[tuple]:
    pts: List[tuple] = []
    if fmt == 0:
        rec = struct.Struct(">hhhBB")
        for i in range(count):
            off = i * 8
            x, y, z, status, cidx = rec.unpack_from(data, off)
            pts.append((x, y, z, status, cidx))
        return pts

    if fmt == 1:
        rec = struct.Struct(">hhBB")  # x,y,status,color_index
        for i in range(count):
            off = i * 6
            x, y, status, cidx = rec.unpack_from(data, off)
            pts.append((x, y, status, cidx))
        return pts

    if fmt == 4:
        # x,y,z,status,r,g,b
        rec = struct.Struct(">hhhBBBB")
        for i in range(count):
            off = i * 10
            x, y, z, status, r, g, b = rec.unpack_from(data, off)
            pts.append((x, y, z, status, r, g, b))
        return pts

    if fmt == 5:
        # x,y,status,r,g,b
        rec = struct.Struct(">hhBBBB")
        for i in range(count):
            off = i * 8
            x, y, status, r, g, b = rec.unpack_from(data, off)
            pts.append((x, y, status, r, g, b))
        return pts

    raise ValueError(f"Unsupported ILDA format {fmt}")


def load_ilda_frames(ilda_path: Union[str, Path]) -> Tuple[List[IldaFrame], Optional[List[RGB]], Dict[str, int]]:
    """
    Returns (frames, embedded_palette, format_counts).

    - frames: concatenation of all supported geometry frames (fmt 0/1/4/5) in file order
    - embedded_palette: palette from fmt 2 blocks if present, else None
    - format_counts: how many ILDA blocks of each format were found (including palette blocks)
    """
    path = Path(ilda_path)
    data = path.read_bytes()

    frames: List[IldaFrame] = []
    embedded_palette: Optional[List[RGB]] = None
    format_counts: Dict[str, int] = {}

    pos = 0
    data_len = len(data)

    # We scan for "ILDA" and parse sequentially.
    while True:
        idx = data.find(ILDA_MAGIC, pos)
        if idx < 0:
            break
        # Need 32 bytes for header
        if idx + ILDA_HEADER_SIZE > data_len:
            break

        try:
            hdr = _parse_header(data[idx:idx + ILDA_HEADER_SIZE])
        except Exception:
            pos = idx + 4
            continue

        fmt = hdr.format_code
        format_counts[str(fmt)] = format_counts.get(str(fmt), 0) + 1

        rec_sz = _record_size(fmt)
        if rec_sz is None:
            # skip unknown/unsupported blocks safely
            # Still advance position as if the block was well formed, if possible.
            payload_len = hdr.num_records * 0
            pos = idx + ILDA_HEADER_SIZE
            continue

        payload_start = idx + ILDA_HEADER_SIZE
        payload_len = hdr.num_records * rec_sz
        payload_end = payload_start + payload_len

        if payload_end > data_len:
            # malformed: stop scanning after this header
            pos = idx + 4
            continue

        payload = data[payload_start:payload_end]

        if fmt == 2:
            # palette block: num_records entries of 3 bytes (r,g,b)
            pal = [(0, 0, 0)] * 256
            n = min(hdr.num_records, 256)
            for i in range(n):
                r, g, b = payload[i * 3:(i + 1) * 3]
                pal[i] = (int(r), int(g), int(b))
            embedded_palette = pal
        elif fmt in (0, 1, 4, 5):
            pts = _parse_records(fmt, payload, hdr.num_records)
            frames.append(IldaFrame(header=hdr, points=pts))

        # Continue scanning after this block's payload
        pos = payload_end

    return frames, embedded_palette, format_counts


# -----------------------------
# Rendering
# -----------------------------

def _compute_bounds(points: Sequence[tuple], fmt: int) -> Tuple[int, int, int, int]:
    # Return (minx, maxx, miny, maxy)
    if not points:
        return (0, 0, 0, 0)

    xs: List[int] = []
    ys: List[int] = []

    if fmt in (0, 4):
        for p in points:
            xs.append(int(p[0]))
            ys.append(int(p[1]))
    elif fmt in (1, 5):
        for p in points:
            xs.append(int(p[0]))
            ys.append(int(p[1]))
    else:
        return (0, 0, 0, 0)

    return (min(xs), max(xs), min(ys), max(ys))


def _map_xy(x: int, y: int, bounds: Tuple[int, int, int, int], size: int, margin: int) -> Tuple[int, int]:
    minx, maxx, miny, maxy = bounds
    spanx = max(1, maxx - minx)
    spany = max(1, maxy - miny)

    # Keep aspect ratio (fit)
    scale = min((size - 2 * margin) / spanx, (size - 2 * margin) / spany)

    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0

    px = (x - cx) * scale + size / 2.0
    # Invert Y for image coordinates
    py = (-(y - cy)) * scale + size / 2.0

    return int(round(px)), int(round(py))


def render_frame_to_image(
    frame: IldaFrame,
    palette: List[RGB],
    image_size: int = 640,
    margin: int = 30,
    point_radius: int = 2,
    line_width: int = 2,
) -> Image.Image:
    """
    Render a single ILDA frame into a PIL Image.
    """
    fmt = frame.header.format_code
    pts = frame.points

    img = Image.new("RGB", (image_size, image_size), (0, 0, 0))
    draw = ImageDraw.Draw(img)


    # avant: bounds = _compute_bounds(pts, fmt)
    # après: filtrer seulement les points dessinables
    def _iter_drawable_points(pts, fmt):
        for p in pts:
            if fmt == 0:
                _x,_y,_z,status,_cidx = p
            elif fmt == 1:
                _x,_y,status,_cidx = p
            elif fmt == 4:
                _x,_y,_z,status,_r,_g,_b = p
            elif fmt == 5:
                _x,_y,status,_r,_g,_b = p
            else:
                continue
            if not _is_blanked(status):
                yield p

    drawable_pts = list(_iter_drawable_points(pts, fmt))
    bounds = _compute_bounds(drawable_pts if drawable_pts else pts, fmt)


    prev_xy: Optional[Tuple[int, int]] = None
    prev_drawable = False
    prev_color: RGB = (255, 255, 255)

    for p in pts:
        if fmt == 0:
            x, y, _z, status, cidx = p
            blanked = _is_blanked(status)
            color = palette[int(cidx) & 0xFF]
        elif fmt == 1:
            x, y, status, cidx = p
            blanked = _is_blanked(status)
            color = palette[int(cidx) & 0xFF]
        elif fmt == 4:
            x, y, _z, status, r, g, b = p
            blanked = _is_blanked(status)
            color = (int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF)
        elif fmt == 5:
            x, y, status, r, g, b = p
            blanked = _is_blanked(status)
            color = (int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF)
        else:
            continue

        xy = _map_xy(int(x), int(y), bounds, image_size, margin)
        drawable = not blanked

        # draw segment
        if prev_xy is not None and prev_drawable and drawable:
            draw.line([prev_xy, xy], fill=prev_color, width=line_width)


        # draw point
        if drawable:
            x0, y0 = xy[0] - point_radius, xy[1] - point_radius
            x1, y1 = xy[0] + point_radius, xy[1] + point_radius
            draw.ellipse([x0, y0, x1, y1], fill=color)

        if blanked:
            prev_xy = None
            prev_drawable = False
        else:
            prev_xy = xy
            prev_drawable = True
            prev_color = color

    return img


# -----------------------------
# Public entry point (GUI)
# -----------------------------

def render_ilda_preview(
    ilda_path: Union[str, Path],
    out_png: Union[str, Path],
    frame_index: int = 1,
    palette_name: Optional[str] = None,
    image_size: int = 640,
) -> Path:
    """
    Generate a PNG preview for one frame of an ILDA file.

    Parameters
    ----------
    ilda_path:
        Path to .ild
    out_png:
        Where to write the PNG
    frame_index:
        1-based index (GUI-friendly). Values <=0 will be treated as 1.
    palette_name:
        Palette for indexed formats (0/1). If None, uses env var ILDA_PREVIEW_PALETTE, else 'idtf14'.
        True-color formats (4/5) ignore this.
    image_size:
        Output PNG size (square).
    """
    ilda_path = Path(ilda_path)
    out_png = Path(out_png)

    frames, embedded_palette, fmt_counts = load_ilda_frames(ilda_path)

    if not frames:
        known = ", ".join(sorted(fmt_counts.keys())) or "none"
        raise ValueError(
            f"No supported ILDA geometry frames found in file. "
            f"Formats seen in file: {known}. "
            f"Supported: 0,1,4,5."
        )

    # 1-based indexing
    idx = int(frame_index) if frame_index is not None else 1
    if idx <= 0:
        idx = 1
    if idx > len(frames):
        idx = len(frames)

    frame = frames[idx - 1]

    # Choose palette for indexed formats
    if frame.header.format_code in (0, 1):
        if embedded_palette is not None:
            pal = embedded_palette
        else:
            pal_name = palette_name or os.getenv("ILDA_PREVIEW_PALETTE") or "idtf14"
            pal = get_palette_by_name(pal_name)
    else:
        # true-color: palette irrelevant
        pal = palette_idtf14()

    img = render_frame_to_image(frame, pal, image_size=image_size)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    return out_png

