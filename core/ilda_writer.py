# core/ilda_writer.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
import struct


@dataclass
class IldaPoint:
    """
    Représente un point ILDA logique.

    x, y, z : coordonnées normalisées dans [-1.0, 1.0]
    color_index : index de palette (0..255)
    blanked : True = déplacement (laser OFF)
    """
    x: float
    y: float
    z: float = 0.0
    color_index: int = 255
    blanked: bool = False


def _clamp_int16(v: float) -> int:
    """
    Mappe un float [-1.0, 1.0] vers un int16 signé.
    """
    i = int(round(v * 32767))
    return max(-32768, min(32767, i))


def write_ilda_file(
    path: str | Path,
    frames: Sequence[Sequence[IldaPoint]],
    *,
    format_code: int = 1,          # 0 = 3D, 1 = 2D
    frame_name: str = "FRAME",
    company_name: str = "LASER",
    projector: int = 0,
) -> Path:
    """
    Écrit un fichier ILDA multi-frames (types 0 ou 1, couleur indexée).

    - path : chemin du fichier .ild à créer
    - frames : liste de frames, chacune étant une liste de IldaPoint
    - format_code : 0 = 3D, 1 = 2D (couleurs indexées)
    """
    path = Path(path)
    total_frames = len(frames)

    with path.open("wb") as f:
        for frame_index, points in enumerate(frames):
            num_records = len(points)

            # --- En-tête 32 octets ---
            header = bytearray(32)
            header[0:4] = b"ILDA"    # signature
            # 4..7 restent à 0
            header[8] = format_code & 0xFF

            # Nom de frame (8 octets max, padding \0)
            frame_name_bytes = frame_name.encode("ascii", "replace")[:8]
            header[9:17] = frame_name_bytes.ljust(8, b"\0")

            # Nom de société (8 octets)
            company_bytes = company_name.encode("ascii", "replace")[:8]
            header[17:25] = company_bytes.ljust(8, b"\0")

            # nb d'enregistrements, frame#, total_frames (uint16 big-endian)
            header[25:27] = struct.pack(">H", num_records)
            header[27:29] = struct.pack(">H", frame_index)
            header[29:31] = struct.pack(">H", total_frames)

            # projecteur
            header[31] = projector & 0xFF

            f.write(header)

            # --- Points ---
            last_index = num_records - 1
            for i, p in enumerate(points):
                status = 0
                if p.blanked:
                    status |= 0x40  # blanking
                if i == last_index:
                    status |= 0x80  # dernier point de la frame

                x_i = _clamp_int16(p.x)
                y_i = _clamp_int16(p.y)
                color_index = max(0, min(255, int(p.color_index)))

                if format_code == 0:
                    z_i = _clamp_int16(p.z)
                    # >hhhBB : x, y, z, status, color_index
                    record = struct.pack(">hhhBB", x_i, y_i, z_i, status, color_index)
                elif format_code == 1:
                    # >hhBB : x, y, status, color_index
                    record = struct.pack(">hhBB", x_i, y_i, status, color_index)
                else:
                    raise ValueError(f"Format ILDA non géré (format_code={format_code})")

                f.write(record)

    return path
