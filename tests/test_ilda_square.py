# tests/test_ilda_square.py

import sys
from pathlib import Path

# --- Ajouter la racine du projet au PYTHONPATH ---
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.step_ilda import write_demo_square


if __name__ == "__main__":
    out_dir = ROOT / "projects" / "test_shapes"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = out_dir / "test_square.ild"
    write_demo_square(out_path)

    print(f"ILDA carré écrit dans : {out_path}")
