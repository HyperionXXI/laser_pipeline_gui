from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SettingsService:
    def __init__(self, *, projects_root: Path, filename: str = "settings.json") -> None:
        self._projects_root = projects_root
        self._filename = filename

    def _settings_path(self, project: str) -> Path:
        return self._projects_root / project / self._filename

    def load(self, project: str) -> dict[str, Any] | None:
        if not project:
            return None
        path = self._settings_path(project)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None

    def save(self, project: str, data: dict[str, Any]) -> bool:
        if not project:
            return False
        path = self._settings_path(project)
        if not path.parent.exists():
            return False
        try:
            payload = json.dumps(
                data,
                indent=2,
                sort_keys=True,
                ensure_ascii=True,
            )
            path.write_text(payload, encoding="utf-8")
            return True
        except Exception:
            return False
