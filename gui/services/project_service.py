from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.config import PROJECTS_ROOT


@dataclass(frozen=True)
class ProjectInfo:
    name: str
    root: Path


class ProjectService:
    """Filesystem operations related to projects (create/open/clear/inspect)."""

    OUTPUT_DIRS = ("frames", "bmp", "svg", "preview", "ilda")

    def project_root(self, project: str) -> Path:
        return PROJECTS_ROOT / project

    def open_project_folder(self, folder: str | Path) -> ProjectInfo:
        root = Path(folder)
        return ProjectInfo(name=root.name, root=root)

    def create_project(self, project: str) -> ProjectInfo:
        root = self.project_root(project)
        for d in ("frames", "bmp", "svg", "ilda", "preview"):
            (root / d).mkdir(parents=True, exist_ok=True)
        return ProjectInfo(name=project, root=root)

    def resolve_ilda_path(self, project_root: Path, project: str) -> Optional[Path]:
        candidates = [
            project_root / f"{project}.ild",
            project_root / "ilda" / f"{project}.ild",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def count_outputs(self, project_root: Path) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.OUTPUT_DIRS:
            p = project_root / d
            if p.exists() and p.is_dir():
                counts[d] = sum(1 for _ in p.glob("*"))
            else:
                counts[d] = 0
        return counts

    def clear_outputs(self, project_root: Path, project: str) -> int:
        deleted = 0
        # clear dirs
        for d in self.OUTPUT_DIRS:
            p = project_root / d
            if not (p.exists() and p.is_dir()):
                continue
            for f in p.glob("*"):
                try:
                    if f.is_file():
                        f.unlink()
                        deleted += 1
                except Exception:
                    pass

        # possible ild at root
        ild_root = project_root / f"{project}.ild"
        if ild_root.exists():
            try:
                ild_root.unlink()
                deleted += 1
            except Exception:
                pass

        return deleted

    def reveal_in_explorer(self, project_root: Path) -> None:
        # Windows friendly. If not available, raise to be handled by UI.
        os.startfile(str(project_root))  # type: ignore[attr-defined]
