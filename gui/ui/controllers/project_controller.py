from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from gui.ui.panels.general_panel import GeneralPanel
from gui.ui.controllers.preview_controller import PreviewController
from gui.ui.controllers.settings_io import apply_ui_state
from gui.services.settings_service import SettingsService
from gui.ui.panels.pipeline_panel import PipelinePanel


class ProjectController:
    def __init__(
        self,
        *,
        parent: QWidget,
        general_panel: GeneralPanel,
        pipeline_panel: PipelinePanel,
        preview_controller: PreviewController,
        projects_root: Path,
        log_fn: Callable[[str], None],
        refresh_previews_fn: Callable[[], None],
        settings_service: SettingsService,
    ) -> None:
        self._parent = parent
        self._general_panel = general_panel
        self._pipeline_panel = pipeline_panel
        self._preview_controller = preview_controller
        self._projects_root = projects_root
        self._log = log_fn
        self._refresh_previews = refresh_previews_fn
        self._settings_service = settings_service

    def choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Choose a video",
            "",
            "Videos (*.mp4 *.mov *.avi);;All files (*)",
        )
        if path:
            self._general_panel.edit_video_path.setText(path)
            self._general_panel.edit_video_path.setFocus()
            self._log(f"Selected video: {path}")

    def create_new_project(self) -> None:
        name, ok = QInputDialog.getText(
            self._parent,
            "Create a project",
            "Project name:",
        )
        if not ok:
            return
        project = (name or "").strip()
        if not project:
            self._log("Error: project name is empty.")
            return

        project_root = self._projects_root / project
        subdirs = ["frames", "bmp", "svg", "ilda", "preview"]
        try:
            for subdir in subdirs:
                (project_root / subdir).mkdir(parents=True, exist_ok=True)
            self._general_panel.edit_project.setText(project)
            self._log(f"Project created: {project_root}")
        except Exception as exc:
            self._log(f"Project creation error: {exc}")

    def open_project(self) -> None:
        root = str(self._projects_root)
        folder = QFileDialog.getExistingDirectory(self._parent, "Open a project", root)
        if not folder:
            return

        try:
            folder_path = Path(folder).resolve()
            project_root = self._projects_root.resolve()
            project_name = folder_path.name

            if folder_path == project_root:
                self._log("[UI] Invalid selection: choose a subfolder of projects/.")
                return

            self._general_panel.edit_project.setText(project_name)
            self._log(f"[UI] Project opened: {project_name}")
            settings = self._settings_service.load(project_name)
            if settings:
                apply_ui_state(
                    settings,
                    general_panel=self._general_panel,
                    pipeline_panel=self._pipeline_panel,
                    preview_controller=self._preview_controller,
                    ignore_project_name=True,
                )
                self._log(f"[Settings] Loaded from {project_name}/settings.json")
            self._refresh_previews()
        except Exception as exc:
            self._log(f"[UI] Open Project error: {exc}")

    def clear_project_outputs(self) -> None:
        project = (self._general_panel.edit_project.text() or "").strip()
        if not project:
            self._log("[UI] Clear outputs: project name is empty.")
            return

        root = self._projects_root / project
        if not root.exists():
            self._log(f"[UI] Clear outputs: missing folder: {root}")
            return

        reply = QMessageBox.question(
            self._parent,
            "Clear outputs",
            (
                "Delete generated outputs in:\n"
                f"{root}\n\n(Frames/BMP/SVG/preview/ilda)\n"
            ),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        deleted = 0
        for sub in ("frames", "bmp", "svg", "preview", "ilda"):
            subdir = root / sub
            if not subdir.exists():
                continue
            for path in subdir.glob("*"):
                try:
                    if path.is_file():
                        path.unlink()
                        deleted += 1
                except Exception:
                    pass

        self._log(f"[UI] Clear outputs: {deleted} files deleted.")
        self._refresh_previews()

    def reveal_project_in_explorer(self) -> None:
        project = (self._general_panel.edit_project.text() or "").strip()
        if not project:
            self._log("[UI] Reveal: project name is empty.")
            return
        path = self._projects_root / project
        if not path.exists():
            self._log(f"[UI] Reveal: missing folder: {path}")
            return
        try:
            os.startfile(str(path))
        except Exception as exc:
            self._log(f"[UI] Reveal error: {exc}")
