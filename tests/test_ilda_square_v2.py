from pathlib import Path
import struct


def _clamp(v: float, vmin: float = -1.0, vmax: float = 1.0) -> float:
    return max(vmin, min(vmax, v))


def _norm_to_int16(v: float) -> int:
    """
    Convertit un float dans [-1.0, 1.0] en coordonnée int16 ILDA.
    On utilise 32767 plutôt que 32768 pour rester dans l’intervalle.
    """
    v = _clamp(v)
    return int(v * 32767)


def write_ilda_header(
    f,
    format_code: int,
    frame_name: str = "SQUARE",
    company_name: str = "PYGEN",
    num_points: int = 0,
    frame_number: int = 0,
    total_frames: int = 1,
    projector: int = 0,
):
    """
    Écrit un header ILDA (32 octets) pour un frame unique.

    Layout (big endian) :
    - 0..3   : 'ILDA'
    - 4..6   : 0x00 0x00 0x00 (reserved)
    - 7      : format code (0,1,2,3,4,5)
    - 8..15  : frame name (8 chars, padded with 0)
    - 16..23 : company name (8 chars, padded with 0)
    - 24..25 : num_points (uint16)
    - 26..27 : frame_number (uint16)
    - 28..29 : total_frames (uint16)
    - 30     : projector (uint8)
    - 31     : reserved (0x00)
    """
    f.write(b"ILDA")
    f.write(b"\x00\x00\x00")          # reserved
    f.write(bytes([format_code]))     # format code

    def pad8(s: str) -> bytes:
        return s.encode("ascii", errors="ignore")[:8].ljust(8, b"\x00")

    f.write(pad8(frame_name))
    f.write(pad8(company_name))

    f.write(struct.pack(">H", num_points))
    f.write(struct.pack(">H", frame_number))
    f.write(struct.pack(">H", total_frames))
    f.write(bytes([projector]))
    f.write(b"\x00")  # reserved


def write_square_v2_ilda(path: Path):
    """
    Écrit un fichier ILDA (format 4 true-color) contenant :
    - un carré fermé (5 points, le dernier revient au premier)
    - chaque vertex d’une couleur différente.
    """

    points = [
        # x,    y,    (R,   G,   B)
        (-0.5, -0.5, (255,   0,   0)),  # bas-gauche  : rouge
        ( 0.5, -0.5, (  0, 255,   0)),  # bas-droite : vert
        ( 0.5,  0.5, (  0,   0, 255)),  # haut-droite: bleu
        (-0.5,  0.5, (255, 255,   0)),  # haut-gauche: jaune
        (-0.5, -0.5, (255, 255, 255)),  # retour au départ : blanc
    ]

    num_points = len(points)

    with open(path, "wb") as f:
        # Header format 4 = true-color, coordonnées 3D + RGB
        write_ilda_header(
            f,
            format_code=4,
            frame_name="SQUARE",
            company_name="PYGEN",
            num_points=num_points,
            frame_number=0,
            total_frames=1,
            projector=0,
        )

        for i, (x, y, (r, g, b)) in enumerate(points):
            xi = _norm_to_int16(x)
            yi = _norm_to_int16(y)
            zi = 0  # reste en 2D

            status = 0x00   # <-- plus de bit "last point"

            # Format 4 record: x, y, z, status, R, G, B
            f.write(struct.pack(">hhhB3B", xi, yi, zi, status, r, g, b))



if __name__ == "__main__":
    out_dir = Path("projects/projet_demo/ilda")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "test_square_v2.ild"
    write_square_v2_ilda(out_path)
    print(f"Écrit : {out_path.resolve()}")
