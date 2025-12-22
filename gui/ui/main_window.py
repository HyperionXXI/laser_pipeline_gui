from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.config import PROJECTS_ROOT
from core.ilda_preview import render_ilda_preview

from gui.pipeline_controller import PipelineController
from gui.ui.menu import build_menu
from gui.ui.panels.pipeline_panel import PipelinePanel


def _now_ts() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Laser Pipeline GUI")

        build_menu(self)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.panel = PipelinePanel(self)
        layout.addWidget(self.panel)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view)

        self.statusBar().showMessage("Ready")

        # Wire panel buttons
        self.panel.btn_browse.clicked.connect(self.choose_video)
        self.panel.btn_test.clicked.connect(self.on_test_click)
        self.panel.btn_preview_frame.clicked.connect(self.on_preview_frame)
        self.panel.btn_ffmpeg.clicked.connect(self.on_ffmpeg_click)
        self.panel.btn_bmp.clicked.connect(self.on_bmp_click)
        self.panel.btn_potrace.clicked.connect(self.on_potrace_click)
        self.panel.btn_ilda.clicked.connect(self.on_export_ilda_click)
        self.panel.btn_run_all.clicked.connect(self.on_execute_all_task)
        self.panel.btn_cancel.clicked.connect(self.on_cancel_task)
        self.panel.combo_ilda_palette.currentIndexChanged.connect(self._on_ilda_preview_palette_changed)

        # Pipeline controller
        self.pipeline = PipelineController(parent=self, log_fn=self.log)
        self.pipeline.step_started.connect(self.on_step_started)
        self.pipeline.step_finished.connect(self.on_step_finished)
        self.pipeline.step_error.connect(self.on_step_error)
        self.pipeline.step_progress.connect(self.on_step_progress)

    # ---------------- Logging & busy ----------------
    def log(self, text: str) -> None:
        self.log_view.append(f"{_now_ts()} {text}")
        self.log_view.moveCursor(QTextCursor.End)
        self.log_view.ensureCursorVisible()

    def set_busy(self, busy: bool, label: str = "") -> None:
        if busy:
            self.panel.progress_bar.setVisible(True)
            self.panel.progress_bar.setRange(0, 0)
            self.panel.btn_cancel.setEnabled(True)
            self.statusBar().showMessage(label or "Working…")
        else:
            self.panel.progress_bar.setRange(0, 100)
            self.panel.progress_bar.setValue(0)
            self.panel.progress_bar.setVisible(False)
            self.panel.btn_cancel.setEnabled(False)
            self.panel.btn_cancel.setText("Annuler la tâche en cours")
            self.statusBar().showMessage("Ready")

        run_enabled = not busy
        for w in (
            self.panel.btn_run_all,
            self.panel.btn_ffmpeg,
            self.panel.btn_bmp,
            self.panel.btn_potrace,
            self.panel.btn_ilda,
            self.panel.btn_preview_frame,
            self.panel.edit_video_path,
            self.panel.edit_project,
            self.panel.spin_fps,
            self.panel.spin_frame,
            self.panel.spin_bmp_threshold,
            self.panel.check_bmp_thinning,
            self.panel.spin_bmp_max_frames,
            self.panel.combo_ilda_mode,
        ):
            w.setEnabled(run_enabled)

    # ---------------- Project helpers ----------------
    def _project_root(self, project: str) -> Path:
        return PROJECTS_ROOT / project

    def _resolve_ilda_path(self, project_root: Path, project: str) -> Optional[Path]:
        candidates = [
            project_root / f"{project}.ild",
            project_root / "ilda" / f"{project}.ild",
        ]
        for p in candidates:
            if p.exists():
                return p
        return None

    def _get_ilda_preview_palette_name(self) -> str:
        key = self.panel.combo_ilda_palette.currentData()
        return str(key) if key else "ilda64"

    # ---------------- Slots pipeline ----------------
    @Slot(str)
    def on_step_started(self, step_name: str) -> None:
        self.set_busy(True, label=f"{step_name}…")
        self.log(f"[{step_name}] démarrage…")

    @Slot(str, object)
    def on_step_finished(self, step_name: str, result: object) -> None:
        self.set_busy(False)
        msg = getattr(result, "message", "")
        if msg:
            self.log(f"[{step_name}] {msg}")

        if step_name in ("ilda", "full_pipeline") and getattr(result, "success", False):
            project = (self.panel.edit_project.text() or "").strip()
            if project:
                self._update_ilda_preview(project)

    @Slot(str, str)
    def on_step_error(self, step_name: str, message: str) -> None:
        self.set_busy(False)
        self.log(f"[{step_name}] ERREUR : {message}")

    @Slot(str, object)
    def on_step_progress(self, step_name: str, payload: object) -> None:
        # payload is our internal _FrameProgress; keep it duck-typed
        total = getattr(payload, "total_frames", None)
        idx = getattr(payload, "frame_index", 0)
        frame_path = getattr(payload, "frame_path", None)

        if total is not None and total > 0:
            self.panel.progress_bar.setRange(0, 100)
            pct = int(max(0, min(int(idx), int(total))) * 100 / int(total))
            self.panel.progress_bar.setValue(pct)
        else:
            self.panel.progress_bar.setRange(0, 0)

        if not frame_path:
            return
        path = str(frame_path)

        if step_name == "ffmpeg":
            self.panel.preview_png.show_image(path)
        elif step_name == "bitmap":
            self.panel.preview_bmp.show_image(path)
        elif step_name == "potrace":
            self.panel.preview_svg.show_svg(path)
        elif step_name == "ilda":
            self.panel.preview_ilda.show_image(path)

    # ---------------- Menu actions ----------------
    def toggle_fullscreen(self) -> None:
        self.setWindowState(self.windowState() ^ self.windowState().WindowFullScreen)

    def choose_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choisir une vidéo",
            "",
            "Vidéos (*.mp4 *.mov *.avi);;Tous les fichiers (*)",
        )
        if path:
            self.panel.edit_video_path.setText(path)
            self.log(f"Vidéo sélectionnée : {path}")

    def open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Ouvrir un projet",
            str(PROJECTS_ROOT),
        )
        if not folder:
            return

        project_root = Path(folder)
        project = project_root.name

        self.panel.edit_project.setText(project)
        self.log(f"[Project] Ouverture : {project_root}")

        self.on_preview_frame()
        self.on_test_click()

    def reveal_project_in_explorer(self) -> None:
        project = (self.panel.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur : nom de projet vide.")
            return
        root = self._project_root(project)
        if not root.exists():
            self.log(f"Erreur : dossier projet inexistant : {root}")
            return
        try:
            os.startfile(str(root))
        except Exception as e:
            self.log(f"Reveal failed: {e}")

    def clear_project_outputs(self) -> None:
        project = (self.panel.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur : nom de projet vide.")
            return
        root = self._project_root(project)
        if not root.exists():
            self.log(f"Erreur : dossier projet inexistant : {root}")
            return

        confirm = QMessageBox.question(
            self,
            "Clear outputs",
            f"Supprimer le contenu généré (frames/bmp/svg/preview/ilda) pour:\n{root} ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        targets = ["frames", "bmp", "svg", "preview", "ilda"]
        deleted = 0
        for d in targets:
            p = root / d
            if p.exists() and p.is_dir():
                for f in p.glob("*"):
                    try:
                        if f.is_file():
                            f.unlink()
                            deleted += 1
                    except Exception:
                        pass

        ild_root = root / f"{project}.ild"
        if ild_root.exists():
            try:
                ild_root.unlink()
                deleted += 1
            except Exception:
                pass

        self.panel.preview_png.clear()
        self.panel.preview_bmp.clear()
        self.panel.preview_svg.clear()
        self.panel.preview_ilda.clear()
        self.log(f"[Project] Outputs cleared. Deleted files: {deleted}")

    def on_new_project(self) -> None:
        name, ok = QInputDialog.getText(self, "Créer un projet", "Nom du projet:")
        if not ok:
            return
        project = (name or "").strip()
        if not project:
            self.log("Erreur : nom de projet vide.")
            return

        project_root = PROJECTS_ROOT / project
        subdirs = ["frames", "bmp", "svg", "ilda", "preview"]
        try:
            for d in subdirs:
                (project_root / d).mkdir(parents=True, exist_ok=True)
            self.panel.edit_project.setText(project)
            self.log(f"Projet créé : {project_root}")
            self.on_preview_frame()
        except Exception as e:
            self.log(f"Erreur création projet : {e}")

    def on_about(self) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("About Laser Pipeline GUI")
        msg.setIcon(QMessageBox.Information)
        msg.setText("Laser Pipeline GUI\n\nExperimental video → ILDA pipeline.")
        msg.exec()

    # ---------------- Buttons ----------------
    def on_test_click(self) -> None:
        video = (self.panel.edit_video_path.text() or "").strip()
        project = (self.panel.edit_project.text() or "").strip()
        fps = self.panel.spin_fps.value()

        self.log("=== Paramètres actuels ===")
        self.log(f"Vidéo : {video or '<aucune>'}")
        self.log(f"Projet : {project or '<vide>'}")
        self.log(f"FPS    : {fps}")
        if project:
            root = self._project_root(project)
            self.log(f"Root   : {root}")
            self.log(f"Exists : {root.exists()}")
            if root.exists():
                counts = {}
                for sub in ("frames", "bmp", "svg", "preview", "ilda"):
                    p = root / sub
                    counts[sub] = len(list(p.glob('*'))) if p.exists() else 0
                self.log(f"Counts : {counts}")
                ild = self._resolve_ilda_path(root, project)
                self.log(f"ILDA   : {ild if ild else '<absent>'}")
        mode_key = self.panel.combo_ilda_mode.currentData() or "classic"
        self.log(f"Mode ILDA : {self.panel.combo_ilda_mode.currentText()} ({mode_key})")
        self.log("==========================")

    def on_ffmpeg_click(self) -> None:
        video = (self.panel.edit_video_path.text() or "").strip()
        project = (self.panel.edit_project.text() or "").strip()
        fps = self.panel.spin_fps.value()

        if not video:
            self.log("Erreur FFmpeg : aucun fichier vidéo sélectionné.")
            return
        if not project:
            self.log("Erreur FFmpeg : nom de projet vide.")
            return

        self.log("[FFmpeg] Démarrage extraction frames…")
        self.pipeline.start_ffmpeg(video, project, fps)

    def on_bmp_click(self) -> None:
        project = (self.panel.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur BMP : nom de projet vide.")
            return

        threshold = self.panel.spin_bmp_threshold.value()
        thinning = self.panel.check_bmp_thinning.isChecked()
        max_frames_val = self.panel.spin_bmp_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None

        self.log(
            f"[BMP] Conversion PNG -> BMP (threshold={threshold}%, thinning={thinning}, "
            f"max_frames={max_frames or 'toutes'})…"
        )
        self.pipeline.start_bitmap(project, threshold, thinning, max_frames)

    def on_potrace_click(self) -> None:
        project = (self.panel.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur Potrace : nom de projet vide.")
            return
        self.log(f"[Potrace] Vectorisation BMP -> SVG pour '{project}'…")
        self.pipeline.start_potrace(project)

    def on_export_ilda_click(self) -> None:
        project = (self.panel.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur ILDA : nom de projet vide.")
            return
        mode_key = self.panel.combo_ilda_mode.currentData() or "classic"
        mode_label = self.panel.combo_ilda_mode.currentText()
        self.log(f"[ILDA] Export ILDA (profil={mode_label})…")
        self.pipeline.start_ilda(project, ilda_mode=str(mode_key))

    def on_cancel_task(self) -> None:
        if not self.panel.btn_cancel.isEnabled():
            return
        self.panel.btn_cancel.setEnabled(False)
        self.panel.btn_cancel.setText("Annulation…")
        self.log("[UI] Annulation demandée…")
        self.pipeline.cancel_current_step()

    def _on_ilda_preview_palette_changed(self, _index: int) -> None:
        try:
            self.on_preview_frame()
        except Exception:
            pass

    def _update_ilda_preview(self, project: str) -> None:
        root = self._project_root(project)
        preview_dir = root / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

        ilda_path = self._resolve_ilda_path(root, project)
        if ilda_path is None:
            self.log("[Preview] Aucun fichier ILDA trouvé.")
            return

        out_png = preview_dir / "ilda_preview.png"
        try:
            render_ilda_preview(
                ilda_path,
                out_png,
                frame_index=0,
                palette_name=self._get_ilda_preview_palette_name(),
            )
            self.panel.preview_ilda.show_image(str(out_png))
            self.log(f"[Preview] ILDA : {out_png}")
        except Exception as e:
            self.log(f"[Preview] Impossible de générer la preview ILDA : {e}")

    def on_preview_frame(self) -> None:
        project = (self.panel.edit_project.text() or "").strip()
        if not project:
            self.log("Erreur preview : nom de projet vide.")
            return

        ui_frame = self.panel.spin_frame.value()
        root = self._project_root(project)

        png = root / "frames" / f"frame_{ui_frame:04d}.png"
        bmp = root / "bmp" / f"frame_{ui_frame:04d}.bmp"
        svg = root / "svg" / f"frame_{ui_frame:04d}.svg"

        if png.exists():
            self.panel.preview_png.show_image(str(png))
        if bmp.exists():
            self.panel.preview_bmp.show_image(str(bmp))
        if svg.exists():
            self.panel.preview_svg.show_svg(str(svg))

        ilda_path = self._resolve_ilda_path(root, project)
        if ilda_path is not None:
            preview_dir = root / "preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            out_png = preview_dir / f"ilda_preview_{ui_frame:04d}.png"
            try:
                render_ilda_preview(
                    ilda_path,
                    out_png,
                    frame_index=max(0, ui_frame - 1),
                    palette_name=self._get_ilda_preview_palette_name(),
                )
                self.panel.preview_ilda.show_image(str(out_png))
            except Exception as e:
                self.log(f"[Preview] ILDA preview error : {e}")

    def on_execute_all_task(self) -> None:
        video = (self.panel.edit_video_path.text() or "").strip()
        project = (self.panel.edit_project.text() or "").strip()
        fps = self.panel.spin_fps.value()

        if not video:
            self.log("Erreur : aucun fichier vidéo sélectionné.")
            return
        if not project:
            self.log("Erreur : nom de projet vide.")
            return

        threshold = self.panel.spin_bmp_threshold.value()
        thinning = self.panel.check_bmp_thinning.isChecked()
        max_frames_val = self.panel.spin_bmp_max_frames.value()
        max_frames = max_frames_val if max_frames_val > 0 else None

        mode_key = self.panel.combo_ilda_mode.currentData() or "classic"
        mode_label = self.panel.combo_ilda_mode.currentText()

        self.log("Démarrage du pipeline complet (4 steps)…")
        self.log(f"  Vidéo   : {video}")
        self.log(f"  Projet  : {project}")
        self.log(f"  FPS     : {fps}")
        self.log(f"  Bitmap  : threshold={threshold}%, thinning={thinning}, max_frames={max_frames or 'toutes'}")
        self.log(f"  ILDA    : profil={mode_label} ({mode_key})")

        self.pipeline.start_full_pipeline(
            video_path=video,
            project=project,
            fps=fps,
            threshold=threshold,
            use_thinning=thinning,
            max_frames=max_frames,
            ilda_mode=str(mode_key),
        )


def run() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(1200, 700)
    win.show()
    sys.exit(app.exec())
