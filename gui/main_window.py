# gui/main_window.py
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTextEdit,
    QVBoxLayout,
    QMessageBox,
)

from core.config import PROJECTS_ROOT
from .pipeline_controller import PipelineController
from gui.services.pipeline_service import PipelineService
from gui.ui.menu import setup_menus, MenuCallbacks
from gui.ui.controllers.pipeline_ui_controller import PipelineUiController
from gui.ui.controllers.preview_controller import PreviewController
from gui.ui.controllers.project_controller import ProjectController
from gui.ui.panels.general_panel import GeneralPanel
from gui.ui.panels.pipeline_panel import PipelinePanel


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Laser Pipeline GUI")

        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # ----------------------------------------------------------
        # General settings
        # ----------------------------------------------------------
        self.general_panel = GeneralPanel(self)
        main_layout.addWidget(self.general_panel)

        # ----------------------------------------------------------
        # Pipeline
        # ----------------------------------------------------------
        self.pipeline_panel = PipelinePanel(self)
        main_layout.addWidget(self.pipeline_panel)

        # ----------------------------------------------------------
        # Log
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        main_layout.addWidget(self.log_view)

        # Pipeline controller
        self.pipeline = PipelineController(parent=self, log_fn=self.log)
        self.pipeline_service = PipelineService(self.pipeline)
        self.preview_controller = PreviewController(
            general_panel=self.general_panel,
            pipeline_panel=self.pipeline_panel,
            projects_root=PROJECTS_ROOT,
            log_fn=self.log,
        )
        self.pipeline_ui = PipelineUiController(
            general_panel=self.general_panel,
            pipeline_panel=self.pipeline_panel,
            preview_controller=self.preview_controller,
            pipeline_service=self.pipeline_service,
            pipeline_controller=self.pipeline,
            log_fn=self.log,
        )
        self.project_controller = ProjectController(
            parent=self,
            general_panel=self.general_panel,
            projects_root=PROJECTS_ROOT,
            log_fn=self.log,
            refresh_previews_fn=self.preview_controller.refresh_previews,
        )

        setup_menus(
            self,
            MenuCallbacks(
                on_new_project=self.project_controller.create_new_project,
                on_open_project=self.project_controller.open_project,
                on_open_video=self.project_controller.choose_video,
                on_clear_outputs=self.project_controller.clear_project_outputs,
                on_reveal_project=self.project_controller.reveal_project_in_explorer,
                on_refresh_previews=self.preview_controller.refresh_previews,
                on_toggle_fullscreen=self.toggle_fullscreen,
                on_about=self.on_about,
                on_exit=self.close,
            ),
        )

        # Wire handlers
        self.general_panel.btn_browse_video.clicked.connect(
            self.project_controller.choose_video
        )
        self.general_panel.btn_test.clicked.connect(self.pipeline_ui.on_test_click)
        self.pipeline_panel.btn_preview_frame.clicked.connect(
            self.pipeline_ui.on_preview_frame
        )
        self.pipeline_panel.btn_run_all.clicked.connect(
            self.pipeline_ui.on_execute_all_task
        )
        self.pipeline_panel.btn_cancel.clicked.connect(self.pipeline_ui.on_cancel_task)
        self.pipeline_panel.btn_ffmpeg.clicked.connect(self.pipeline_ui.on_ffmpeg_click)
        self.pipeline_panel.btn_bmp.clicked.connect(self.pipeline_ui.on_bmp_click)
        self.pipeline_panel.btn_potrace.clicked.connect(self.pipeline_ui.on_potrace_click)
        self.pipeline_panel.btn_arcade.clicked.connect(self.pipeline_ui.on_arcade_click)
        self.pipeline_panel.btn_ilda.clicked.connect(self.pipeline_ui.on_export_ilda_click)
        self.pipeline_panel.combo_ilda_palette.currentIndexChanged.connect(
            self.preview_controller.on_palette_changed
        )

        self.pipeline.step_started.connect(self.pipeline_ui.on_step_started)
        self.pipeline.step_finished.connect(self.pipeline_ui.on_step_finished)
        self.pipeline.step_error.connect(self.pipeline_ui.on_step_error)
        self.pipeline.step_progress.connect(self.pipeline_ui.on_step_progress)

        self.pipeline_panel.update_mode_ui()

        self._apply_style()

    # ---------------- Logging ------------------------------------

    def log(self, text: str) -> None:
        ts = datetime.now().strftime("[%H:%M:%S]")
        self.log_view.append(f"{ts} {text}")
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.ensureCursorVisible()

    def on_about(self) -> None:
        readme_text = ""
        try:
            readme_path = Path(__file__).resolve().parent.parent / "README.md"
            if readme_path.exists():
                readme_text = readme_path.read_text(encoding="utf-8")
        except Exception as e:
            readme_text = f"(Could not load README.md: {e})"

        msg = QMessageBox(self)
        msg.setWindowTitle("About Laser Pipeline GUI")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Laser Pipeline GUI\n\nExperimental video -> ILDA pipeline.")
        if readme_text:
            msg.setDetailedText(readme_text)
        msg.exec()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def _apply_style(self) -> None:
        self.setStyleSheet("")



def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())

