# core/ilda_writer.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


# ======================================================================
# Structures
# ======================================================================

@dataclass
class IldaPoint:
    x: int
    y: int
    z: int = 0
    blanked: bool = False
    color_index: int = 0
    r: Optional[int] = None
    g: Optional[int] = None
    b: Optional[int] = None


@dataclass
class IldaFrame:
    name: str = ""
    company: str = "LPIP"
    points: List[IldaPoint] | None = None
    projector: int = 0

    def ensure_points(self) -> List[IldaPoint]:
        if self.points is None:
            self.points = []
        return self.points


# ======================================================================
# Header générique
# ======================================================================

def _build_ilda_header(
    *,
    format_code: int,
    name: str,
    company: str,
    num_records: int,
    seq_no: int,
    total_frames: int,
    projector: int = 0,
) -> bytes:
    header = bytearray(32)
    header[0:4] = b"ILDA"
    header[4:7] = b"\x00\x00\x00"
    header[7] = format_code & 0xFF

    header[8:16] = name.encode("ascii", "ignore")[:8].ljust(8, b"\x00")
    header[16:24] = company.encode("ascii", "ignore")[:8].ljust(8, b"\x00")
    header[24:26] = num_records.to_bytes(2, "big")
    header[26:28] = seq_no.to_bytes(2, "big")
    header[28:30] = total_frames.to_bytes(2, "big")
    header[30] = projector & 0xFF
    header[31] = 0
    return bytes(header)


# ======================================================================
# Écriture TRUE COLOR (format 5)
# ======================================================================

def write_ilda_truecolor(path: str | Path, frames: Iterable[IldaFrame]) -> Path:
    out_path = Path(path)
    frames_list = list(frames)
    total_frames = len(frames_list)

    with out_path.open("wb") as f:
        for seq_no, frame in enumerate(frames_list):
            pts = frame.ensure_points()
            header = _build_ilda_header(
                format_code=5,
                name=frame.name,
                company=frame.company,
                num_records=len(pts),
                seq_no=seq_no,
                total_frames=total_frames,
                projector=frame.projector,
            )
            f.write(header)

            for i, p in enumerate(pts):
                status = 0x40 if p.blanked else 0x00
                f.write(
                    int(p.x).to_bytes(2, "big", signed=True) +
                    int(p.y).to_bytes(2, "big", signed=True) +
                    int(p.z).to_bytes(2, "big", signed=True) +
                    bytes((
                        status,
                        p.r or 0,
                        p.g or 0,
                        p.b or 0,
                    ))
                )

        # EOF
        eof = _build_ilda_header(
            format_code=5,
            name="",
            company="",
            num_records=0,
            seq_no=total_frames,
            total_frames=total_frames,
            projector=0,
        )
        f.write(eof)

    return out_path


# ======================================================================
# Écriture INDEXED (format 0) — inchangé
# ======================================================================

def write_ilda_indexed(path: str | Path, frames: Iterable[IldaFrame]) -> Path:
    out_path = Path(path)
    frames_list = list(frames)
    total_frames = len(frames_list)

    with out_path.open("wb") as f:
        for seq_no, frame in enumerate(frames_list):
            pts = frame.ensure_points()
            header = _build_ilda_header(
                format_code=0,
                name=frame.name,
                company=frame.company,
                num_records=len(pts),
                seq_no=seq_no,
                total_frames=total_frames,
                projector=frame.projector,
            )
            f.write(header)

            for i, p in enumerate(pts):
                status = 0x80 if i == len(pts) - 1 else 0
                if p.blanked:
                    status |= 0x40
                f.write(
                    int(p.x).to_bytes(2, "big", signed=True) +
                    int(p.y).to_bytes(2, "big", signed=True) +
                    int(p.z).to_bytes(2, "big", signed=True) +
                    bytes((status, p.color_index & 0xFF))
                )

        # EOF
        eof = _build_ilda_header(
            format_code=0,
            name="",
            company="",
            num_records=0,
            seq_no=total_frames,
            total_frames=total_frames,
            projector=0,
        )
        f.write(eof)

    return out_path


# ======================================================================
# Dispatcher
# ======================================================================

def write_ilda_file(
    path: str | Path,
    frames: Iterable[IldaFrame],
    *,
    mode: str = "indexed",
) -> Path:
    if mode == "truecolor":
        return write_ilda_truecolor(path, frames)
    return write_ilda_indexed(path, frames)
