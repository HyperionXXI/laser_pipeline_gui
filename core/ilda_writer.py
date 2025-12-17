"""
core/ilda_writer.py

Writer for ILDA (.ild) files used in this project.

Goals in this repo:
- Keep the ILDA layer *generic* and reusable (no GUI dependencies).
- Produce files that are readable by common tools (LaserShowGen, LaserOS, etc.).
- Be robust against small API changes between exporter/preview modules.

This file intentionally supports TWO calling styles for IldaFrame:

1) "New" style (explicit header):
    frame = IldaFrame(header=IldaHeader(...), points=[...])

2) "Legacy" style (used by ilda_export.py in this repo for a long time):
    frame = IldaFrame(name="F0001", company="LPIP", points=[...], projector=0)

The compatibility layer is here to avoid regressions when other modules evolve.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Union
import struct
from pathlib import Path


# ---------------------------
# Data structures
# ---------------------------

@dataclass(frozen=True)
class IldaHeader:
    """
    ILDA 32-byte header.

    Layout (big-endian):
      0..3   : ASCII "ILDA"
      4..6   : 0x00 0x00 0x00 (reserved)
      7      : format code (0..5 typically)
      8..15  : frame name (8 bytes, ASCII, padded with NUL/space)
      16..23 : company name (8 bytes, ASCII, padded)
      24..25 : number of records (uint16)
      26..27 : frame number (uint16)
      28..29 : total frames (uint16)  (many tools expect "last index", i.e. len(frames)-1)
      30     : scanner head / projector (uint8)
      31     : reserved (uint8)
    """
    format_code: int
    frame_name: str = ""
    company_name: str = ""
    num_records: int = 0
    frame_number: int = 0
    total_frames: int = 0
    scanner_head: int = 0


@dataclass(frozen=True)
class IldaPoint:
    """
    A logical point used by the exporter.

    For INDEXED modes (format 0/1):
      - x, y, (optional z)
      - blanked
      - color_index (0..255)

    For TRUECOLOR modes (format 4/5):
      - x, y, (optional z)
      - blanked
      - r, g, b (0..255)
    """
    x: int
    y: int
    z: int = 0

    blanked: bool = False

    # Indexed color (formats 0/1)
    color_index: int = 0

    # Truecolor (formats 4/5)
    r: Optional[int] = None
    g: Optional[int] = None
    b: Optional[int] = None


class IldaFrame:
    """
    Container for one ILDA frame.

    Compatibility note:
    - Some parts of the repo historically created frames with name/company/projector,
      not a full IldaHeader object.
    - The writer accepts both; internally it always exposes .header and .points.

    Public attributes:
      - header: IldaHeader
      - points: Sequence[IldaPoint]
      - format_code: int (shortcut: header.format_code)
      - record_count: int (shortcut: header.num_records)
    """

    __slots__ = ("header", "points")

    def __init__(
        self,
        header: Optional[IldaHeader] = None,
        points: Optional[Sequence[IldaPoint]] = None,
        # legacy / convenience kwargs:
        name: str = "",
        company: str = "",
        projector: int = 0,
        format_code: Optional[int] = None,
        frame_number: int = 0,
        total_frames: int = 0,
    ) -> None:
        if points is None:
            points = []

        if header is None:
            # If format_code not provided, keep it 0 by default; the writer can override
            # it based on "mode" when writing.
            fc = 0 if format_code is None else int(format_code)
            header = IldaHeader(
                format_code=fc,
                frame_name=str(name or ""),
                company_name=str(company or ""),
                num_records=len(points),
                frame_number=int(frame_number),
                total_frames=int(total_frames),
                scanner_head=int(projector),
            )
        else:
            # Ensure num_records matches points length (source of many subtle ILDA corruptions).
            if header.num_records != len(points):
                header = IldaHeader(
                    format_code=header.format_code,
                    frame_name=header.frame_name,
                    company_name=header.company_name,
                    num_records=len(points),
                    frame_number=header.frame_number,
                    total_frames=header.total_frames,
                    scanner_head=header.scanner_head,
                )

        self.header = header
        self.points = list(points)

    @property
    def format_code(self) -> int:
        return int(self.header.format_code)

    @property
    def record_count(self) -> int:
        return int(self.header.num_records)


# ---------------------------
# Helpers
# ---------------------------

def _clip_i16(v: int) -> int:
    if v < -32768:
        return -32768
    if v > 32767:
        return 32767
    return int(v)

def _clip_u8(v: int) -> int:
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(v)

def _encode_name8(s: str) -> bytes:
    # Most tools accept ASCII; we replace unknown chars.
    b = (s or "").encode("ascii", errors="replace")
    b = b[:8]
    return b.ljust(8, b"\x00")

def _status_byte(blanked: bool, last_point: bool) -> int:
    # ILDA status byte:
    # bit 6 (0x40): blanked (laser off)
    # bit 7 (0x80): last point
    st = 0x40 if blanked else 0x00
    if last_point:
        st |= 0x80
    return st

def _write_header(f, h: IldaHeader) -> None:
    f.write(b"ILDA")
    f.write(b"\x00\x00\x00")
    f.write(struct.pack(">B", _clip_u8(h.format_code)))
    f.write(_encode_name8(h.frame_name))
    f.write(_encode_name8(h.company_name))
    f.write(struct.pack(">H", int(h.num_records) & 0xFFFF))
    f.write(struct.pack(">H", int(h.frame_number) & 0xFFFF))
    f.write(struct.pack(">H", int(h.total_frames) & 0xFFFF))
    f.write(struct.pack(">B", _clip_u8(h.scanner_head)))
    f.write(b"\x00")  # reserved


def _infer_truecolor(points: Sequence[IldaPoint]) -> bool:
    # If any point has explicit r/g/b, we treat as truecolor.
    for p in points:
        if p.r is not None or p.g is not None or p.b is not None:
            return True
    return False


# ---------------------------
# Public writer API
# ---------------------------

def write_ilda_file(
    out_path: Union[str, Path],
    frames: Sequence[IldaFrame],
    *,
    mode: str = "indexed",
    force_format: Optional[int] = None,
    include_eof_header: bool = False,  # <-- NEW (default off)
) -> Path:
    out_path = Path(out_path)

    # Recommended: total_frames = number of frames (not last index)
    total_frames = len(frames)

    with out_path.open("wb") as f:
        for idx, frame in enumerate(frames):
            pts = list(frame.points)

            # Decide format code
            if force_format is not None:
                fmt = int(force_format)
            else:
                if mode.lower() == "truecolor" or _infer_truecolor(pts):
                    fmt = 5
                else:
                    fmt = 0

            h0 = frame.header
            h = IldaHeader(
                format_code=fmt,
                frame_name=h0.frame_name,
                company_name=h0.company_name,
                num_records=len(pts),
                frame_number=idx,
                total_frames=total_frames,   # <-- FIXED
                scanner_head=h0.scanner_head,
            )

            _write_header(f, h)

            for p_i, p in enumerate(pts):
                last_point = (p_i == len(pts) - 1)
                st = _status_byte(bool(p.blanked), last_point)

                if fmt == 0:
                    rec = struct.pack(
                        ">hhhBB",
                        _clip_i16(p.x),
                        _clip_i16(p.y),
                        _clip_i16(p.z),
                        _clip_u8(st),
                        _clip_u8(p.color_index),
                    )
                    f.write(rec)

                elif fmt == 1:
                    rec = struct.pack(
                        ">hhBB",
                        _clip_i16(p.x),
                        _clip_i16(p.y),
                        _clip_u8(st),
                        _clip_u8(p.color_index),
                    )
                    f.write(rec)

                elif fmt == 4:
                    r = 255 if p.r is None else p.r
                    g = 255 if p.g is None else p.g
                    b = 255 if p.b is None else p.b
                    rec = struct.pack(
                        ">hhhBBBB",
                        _clip_i16(p.x),
                        _clip_i16(p.y),
                        _clip_i16(p.z),
                        _clip_u8(st),
                        _clip_u8(r),
                        _clip_u8(g),
                        _clip_u8(b),
                    )
                    f.write(rec)

                elif fmt == 5:
                    # 2D truecolor: x,y,status,r,g,b => 8 bytes
                    r = 255 if p.r is None else p.r
                    g = 255 if p.g is None else p.g
                    b = 255 if p.b is None else p.b
                    rec = struct.pack(
                        ">hhBBBB",
                        _clip_i16(p.x),
                        _clip_i16(p.y),
                        _clip_u8(st),
                        _clip_u8(r),
                        _clip_u8(g),
                        _clip_u8(b),
                    )
                    f.write(rec)

                else:
                    raise ValueError(f"Unsupported ILDA format code for writer: {fmt}")

        # Optional EOF header (some readers like it, others treat it as a frame)
        if include_eof_header:
            eof = IldaHeader(
                format_code=0,
                frame_name="",
                company_name="",
                num_records=0,
                frame_number=0,
                total_frames=0,
                scanner_head=0,
            )
            _write_header(f, eof)

    return out_path
