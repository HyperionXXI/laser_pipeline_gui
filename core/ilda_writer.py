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
    Les coordonnées sont attendues déjà normalisées dans l'intervalle
    [-32768, +32767] pour X/Y/Z.
    """
    x: int
    y: int
    z: int = 0
    blanked: bool = False
    color_index: int = 255  # index dans la palette ILDA standard (0–255)


@dataclass
class IldaFrame:
    """
    Une frame ILDA (un dessin / état d'animation).
    """
    name: str = ""
    company: str = "LPIP"
    points: List[IldaPoint] | None = None
    projector: int = 0  # numéro de projecteur (0–255)

    def ensure_points(self) -> List[IldaPoint]:
        if self.points is None:
            self.points = []
        return self.points


# ======================================================================
# Header ILDA – implémentation stricte de la spec
# ======================================================================


def _build_ilda_header_3d(
    frame: IldaFrame,
    num_points: int,
    seq_no: int,
    total_frames: int,
) -> bytes:
    """
    Construit un header ILDA 3D indexed (format code = 0) de 32 octets.

    Spécification (ILDA Image Data Transfer Format) – "3D coordinate image".
    Offsets (0-based) :

      0–3   : "ILDA"
      4–6   : 3 octets réservés = 0
      7     : format code (0 = 3D indexed)
      8–15  : nom de frame (8 chars, padded avec 0)
      16–23 : nom société (8 chars, padded avec 0)
      24–25 : nombre de points (uint16 big-endian)
      26–27 : numéro de frame (uint16 big-endian)
      28–29 : nombre total de frames dans le fichier (uint16 big-endian)
      30    : numéro de projecteur (0–255)
      31    : réservé = 0
    """
    header = bytearray(32)

    # "ILDA"
    header[0:4] = b"ILDA"

    # 3 octets réservés
    header[4:7] = b"\x00\x00\x00"

    # format code (0 = 3D indexed)
    header[7] = 0

    # Nom de frame (max 8 caractères ASCII)
    name_bytes = (frame.name or "").encode("ascii", errors="ignore")[:8]
    header[8:16] = name_bytes.ljust(8, b"\x00")

    # Nom de société (max 8 caractères ASCII)
    company_bytes = (frame.company or "").encode("ascii", errors="ignore")[:8]
    header[16:24] = company_bytes.ljust(8, b"\x00")

    # Nombre de points
    header[24:26] = int(num_points).to_bytes(2, "big", signed=False)

    # Numéro de frame (seq_no)
    header[26:28] = int(seq_no).to_bytes(2, "big", signed=False)

    # Nombre total de frames dans le fichier (hors frame EOF)
    header[28:30] = int(total_frames).to_bytes(2, "big", signed=False)

    # Projecteur
    header[30] = int(frame.projector) & 0xFF

    # Dernier octet réservé = 0
    header[31] = 0

    return bytes(header)


def _pack_ilda_point(pt: IldaPoint, is_last: bool) -> bytes:
    """
    Sérialise un point ILDA 3D indexed (format code 0).

    Layout (8 octets) :

      X : int16 big-endian
      Y : int16 big-endian
      Z : int16 big-endian
      Status : 1 octet (bit7 = last point, bit6 = blanked)
      Color index : 1 octet
    """
    # Status bits
    status = 0
    if is_last:
        status |= 0x80  # last point
    if pt.blanked:
        status |= 0x40  # blanking

    return (
        int(pt.x).to_bytes(2, "big", signed=True) +
        int(pt.y).to_bytes(2, "big", signed=True) +
        int(pt.z).to_bytes(2, "big", signed=True) +
        bytes((status & 0xFF, int(pt.color_index) & 0xFF))
    )


# ======================================================================
# Écriture de fichier ILDA
# ======================================================================


def write_ilda_file(path: str | Path, frames: Iterable[IldaFrame]) -> Path:
    """
    Écrit un fichier ILDA contenant une ou plusieurs frames 3D indexed.

    - `frames` : iterable d'IldaFrame (au moins une frame non vide).
    - Une frame EOF spéciale (0 points, num_points=0) est ajoutée en fin
      comme le recommande la spécification.

    Retourne le Path résultant.
    """
    out_path = Path(path)
    frames_list = list(frames)

    # Filtre de sécurité : on enlève toutes les frames réellement vides
    # (0 points). Si tout est vide, on écrit quand même un fichier mais
    # il sera explicitement "empty".
    non_empty_frames: list[IldaFrame] = []
    for fr in frames_list:
        pts = fr.ensure_points()
        if pts:
            non_empty_frames.append(fr)

    if not non_empty_frames:
        # Fichier ILDA minimal avec une seule frame EOF.
        with out_path.open("wb") as f:
            eof = IldaFrame(name="", company="", points=[], projector=0)
            eof_header = _build_ilda_header_3d(
                eof,
                num_points=0,
                seq_no=0,
                total_frames=0,
            )
            f.write(eof_header)
        return out_path

    total_frames = len(non_empty_frames)

    with out_path.open("wb") as f:
        # Frames normales
        for seq_no, frame in enumerate(non_empty_frames):
            pts = frame.ensure_points()
            num_points = len(pts)

            header = _build_ilda_header_3d(
                frame,
                num_points=num_points,
                seq_no=seq_no,
                total_frames=total_frames,
            )
            f.write(header)

            for i, p in enumerate(pts):
                f.write(_pack_ilda_point(p, is_last=(i == num_points - 1)))

        # Frame EOF : header avec num_points=0
        eof_frame = IldaFrame(name="", company="", points=[], projector=0)
        eof_header = _build_ilda_header_3d(
            eof_frame,
            num_points=0,
            seq_no=total_frames,
            total_frames=total_frames,
        )
        f.write(eof_header)

    return out_path


# ======================================================================
# Carré de test (utilisé par les tests unitaires et la doc)
# ======================================================================


def write_test_square(path: str | Path) -> Path:
    """
    Écrit un simple carré dans un fichier ILDA, utile pour des tests
    rapides avec un viewer ILDA / LaserOS.
    """
    out_path = Path(path)

    # Carré dans les coordonnées ILDA (-32768..+32767)
    size = 20000
    left = -size
    right = size
    top = size
    bottom = -size

    pts: list[IldaPoint] = []

    # On commence en blanked pour éviter un trait depuis l'origine
    pts.append(IldaPoint(left, top, 0, blanked=True, color_index=1))       # start
    pts.append(IldaPoint(right, top, 0, blanked=False, color_index=1))     # haut
    pts.append(IldaPoint(right, bottom, 0, blanked=False, color_index=2))  # droite
    pts.append(IldaPoint(left, bottom, 0, blanked=False, color_index=3))   # bas
    pts.append(IldaPoint(left, top, 0, blanked=False, color_index=4))      # gauche

    frame = IldaFrame(
        name="SQUARE",
        company="LPIP",
        points=pts,
        projector=0,
    )

    return write_ilda_file(out_path, [frame])


# Alias historique (certains anciens codes importent write_demo_square)
def write_demo_square(path: str | Path) -> Path:
    return write_test_square(path)
