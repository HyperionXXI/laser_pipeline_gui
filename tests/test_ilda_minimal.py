# test_ilda_minimal.py

from pathlib import Path
import struct


def int16_from_float(v: float) -> int:
    """
    Convertit un float dans [-1.0, +1.0] vers un int16 signé ILDA.
    """
    v = max(-1.0, min(1.0, v))
    return int(v * 32767)


def write_ilda_file(path: Path):
    """
    Écrit un ILDA très simple :
    - 1 frame (format 4 : 2D true-color)
    - 4 points formant un carré.
    """

    path = Path(path)
    points = []

    # Petit carré centré, coordonnées normalisées [-1,1]
    coords = [
        (-0.5, -0.5),
        ( 0.5, -0.5),
        ( 0.5,  0.5),
        (-0.5,  0.5),
    ]

    for i, (xf, yf) in enumerate(coords):
        x = int16_from_float(xf)
        y = int16_from_float(yf)

        # Dernier point ? (bit 6)
        if i == len(coords) - 1:
            status = 0x40
        else:
            status = 0x00

        # Blanc
        r, g, b = 255, 255, 255
        points.append((x, y, status, r, g, b))

    n_points = len(points)

    with path.open("wb") as f:
        # ---------- Header de la frame (format 4 : 2D true-color) ----------
        header = bytearray(32)
        header[0:4] = b"ILDA"
        # bytes 4-6 = reserved = 0
        header[7] = 4  # format 4 = 2D true-color

        frame_name = "TEST"
        company = "GPT"
        header[8:16] = frame_name.encode("ascii", "replace").ljust(8, b"\x00")
        header[16:24] = company.encode("ascii", "replace").ljust(8, b"\x00")

        # nombre de points, frame index, total frames (big endian)
        header[24:26] = struct.pack(">H", n_points)   # record count
        header[26:28] = struct.pack(">H", 0)          # frame number
        header[28:30] = struct.pack(">H", 1)          # total frames = 1

        header[30] = 0  # projector
        header[31] = 0  # reserved

        f.write(header)

        # ---------- Points ----------
        for x, y, status, r, g, b in points:
            f.write(struct.pack(">hhBBBB", x, y, status, r, g, b))

        # ---------- Bloc "End of ILDA" ----------
        end_header = bytearray(32)
        end_header[0:4] = b"ILDA"
        # reserved + format = 0
        # nom de frame / société = vides
        end_header[24:26] = struct.pack(">H", 0)  # 0 records => "end"
        f.write(end_header)

    print(f"Écrit : {path} ({n_points} points)")


if __name__ == "__main__":
    out = Path("test_shapes.ild")
    write_ilda_file(out)
