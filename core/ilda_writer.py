# core/ilda_writer.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


# ======================================================================
# Structures ILDA bas niveau
# ======================================================================

@dataclass
class IldaPoint:
    """
    Point ILDA en coordonnées 3D (Z=0 pour nous) avec blanking et index couleur.
    """
    x: int
    y: int
    z: int = 0
    blanked: bool = False
    color_index: int = 255  # index dans la palette ILDA standard


@dataclass
class IldaFrame:
    """
    Une frame ILDA (un dessin / état d'animation).
    """
    name: str = "FRAME"
    company: str = "LPIP"
    points: List[IldaPoint] | None = None
    projector: int = 0  # 0–255

    def ensure_points(self) -> List[IldaPoint]:
        if self.points is None:
            self.points = []
        return self.points


# ======================================================================
# Writer ILDA (format code 0 = 3D indexed)
# ======================================================================

def _build_ilda_header_3d(
    frame: IldaFrame,
    num_points: int,
    seq_no: int,
    total_frames: int,
) -> bytes:
    """
    Construit un header ILDA 3D (format code 0) de 32 octets.
    Spécification : 3D coordinate image section.
    """
    header = bytearray(32)

    # 1–4 : "ILDA"
    header[0:4] = b"ILDA"

    # 5–8 : format code (32 bits big endian) => 0 pour 3D indexed
    header[4:8] = (0).to_bytes(4, "big", signed=False)

    # 9–16 : frame name (8 bytes, ASCII, padded with 0)
    frame_name = (frame.name or "").encode("ascii", "replace")[:8]
    header[8:16] = frame_name.ljust(8, b"\x00")

    # 17–24 : company name (8 bytes)
    company = (frame.company or "").encode("ascii", "replace")[:8]
    header[16:24] = company.ljust(8, b"\x00")

    # 25–26 : total points in this frame (1..65535, 0 = EOF frame)
    header[24:26] = num_points.to_bytes(2, "big", signed=False)

    # 27–28 : frame number
    header[26:28] = seq_no.to_bytes(2, "big", signed=False)

    # 29–30 : total frames
    header[28:30] = total_frames.to_bytes(2, "big", signed=False)

    # 31 : scanner / projector number
    header[30] = frame.projector & 0xFF

    # 32 : reserved = 0
    header[31] = 0

    return bytes(header)


def _pack_ilda_point(pt: IldaPoint, is_last: bool) -> bytes:
    """
    Encode un point ILDA (3D) :
        X (2 bytes signed)
        Y (2 bytes signed)
        Z (2 bytes signed)
        Status (1 byte)
        Color index (1 byte)
    """
    status = 0
    if is_last:
        status |= 0x80  # last point bit
    if pt.blanked:
        status |= 0x40  # blanking bit

    return (
        int(pt.x).to_bytes(2, "big", signed=True) +
        int(pt.y).to_bytes(2, "big", signed=True) +
        int(pt.z).to_bytes(2, "big", signed=True) +
        bytes((status & 0xFF, pt.color_index & 0xFF))
    )


def write_ilda_file(path: str | Path, frames: Iterable[IldaFrame]) -> Path:
    """
    Écrit un fichier ILDA avec une ou plusieurs frames (3D indexed).
    Ajoute une frame spéciale avec 0 points pour marquer EOF.
    """
    out_path = Path(path)
    frames_list = list(frames)
    total_frames = len(frames_list)

    with out_path.open("wb") as f:
        for seq_no, frame in enumerate(frames_list):
            pts = frame.ensure_points()
            num_points = len(pts)

            header = _build_ilda_header_3d(frame, num_points, seq_no, total_frames)
            f.write(header)

            for i, p in enumerate(pts):
                f.write(_pack_ilda_point(p, is_last=(i == num_points - 1)))

        # Frame EOF : header avec num_points=0
        eof_frame = IldaFrame(name="", company="", points=[])
        eof_header = _build_ilda_header_3d(eof_frame, num_points=0,
                                           seq_no=0, total_frames=0)
        f.write(eof_header)

    return out_path


# ======================================================================
# Démo : carré de test (utilisé par tests/test_ilda_square.py)
# ======================================================================

def write_demo_square(path: str | Path) -> Path:
    """
    Écrit un carré simple, centré, avec 4 couleurs différentes
    sur chaque côté. Utilisable pour les tests.
    """
    out_path = Path(path)

    size = 20000  # +- 20000 dans l'espace ILDA (-32768..32767)
    left, right = -size, size
    bottom, top = -size, size

    pts: List[IldaPoint] = []

    # On part du coin haut-gauche, blanked pour "sauter" depuis n'importe où.
    pts.append(IldaPoint(left,  top,    0, blanked=True,  color_index=1))  # start
    pts.append(IldaPoint(right, top,    0, blanked=False, color_index=1))  # haut
    pts.append(IldaPoint(right, bottom, 0, blanked=False, color_index=2))  # droite
    pts.append(IldaPoint(left,  bottom, 0, blanked=False, color_index=3))  # bas
    pts.append(IldaPoint(left,  top,    0, blanked=False, color_index=4))  # gauche

    frame = IldaFrame(
        name="SQUARE",
        company="LPIP",
        points=pts,
        projector=0,
    )

    return write_ilda_file(out_path, [frame])
