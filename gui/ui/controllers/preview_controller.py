from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QTimer

from gui.services.preview_service import FramePreviewPaths, PreviewService
from gui.ui.panels.general_panel import GeneralPanel
from gui.ui.panels.pipeline_panel import PipelinePanel


class PreviewController:
    def __init__(
        self,
        *,
        general_panel: GeneralPanel,
        pipeline_panel: PipelinePanel,
        projects_root: Path,
        log_fn: Callable[[str], None],
    ) -> None:
        self._general_panel = general_panel
        self._pipeline_panel = pipeline_panel
        self._projects_root = projects_root
        self._log = log_fn
        self._preview_service = PreviewService()
        self._play_timer = QTimer()
        self._play_timer.timeout.connect(self._on_play_tick)
        self._play_active = False
        self._play_frame = 1
        self._play_end_frame = 1

    def set_ilda_title_live(self, live: bool) -> None:
        self._pipeline_panel.set_ilda_title_live(live)

    def refresh_previews(self) -> None:
        self.show_current_frame()

    def set_palette_enabled(self, enabled: bool) -> None:
        self._pipeline_panel.combo_ilda_palette.setEnabled(enabled)

    def get_palette_name(self) -> str:
        return self._get_palette_name()

    def show_current_frame(self) -> None:
        project = (self._general_panel.edit_project.text() or "").strip()
        if not project:
            self._log("Preview error: project name is empty.")
            return
        ui_frame = self._pipeline_panel.spin_frame.value()
        self.show_frame_preview(project, ui_frame)

    def toggle_play(self) -> None:
        if self._play_active:
            self.stop_play()
        else:
            self.start_play()

    def start_play(self) -> None:
        project = (self._general_panel.edit_project.text() or "").strip()
        if not project:
            self._log("Preview error: project name is empty.")
            return
        fps = int(self._general_panel.spin_fps.value())
        if fps <= 0:
            fps = 1
        max_frames_val = int(self._general_panel.spin_max_frames.value())
        project_root = self._projects_root / project
        end_frame = self._resolve_play_end_frame(project_root, max_frames_val)
        if end_frame <= 0:
            self._log("Preview error: no frames available for playback.")
            return
        current = int(self._pipeline_panel.spin_frame.value())
        if current < 1 or current > end_frame:
            current = 1
            self._pipeline_panel.spin_frame.setValue(current)
        self._play_frame = current
        self._play_end_frame = end_frame
        self._play_active = True
        self._pipeline_panel.btn_play.setText("Pause")
        self._pipeline_panel.btn_stop.setEnabled(True)
        self._pipeline_panel.spin_frame.setEnabled(False)
        self._pipeline_panel.btn_preview_frame.setEnabled(False)
        self._play_timer.start(int(1000 / fps))

    def stop_play(self) -> None:
        if not self._play_active:
            return
        self._play_active = False
        self._play_timer.stop()
        self._pipeline_panel.btn_play.setText("Play")
        self._pipeline_panel.btn_stop.setEnabled(False)
        self._pipeline_panel.spin_frame.setEnabled(True)
        self._pipeline_panel.btn_preview_frame.setEnabled(True)

    def _resolve_play_end_frame(self, project_root: Path, max_frames: int) -> int:
        if max_frames > 0:
            return max_frames
        return self._find_max_frame_index(project_root)

    def _find_max_frame_index(self, project_root: Path) -> int:
        max_idx = 0
        for folder, suffix in (("frames", ".png"), ("bmp", ".bmp"), ("svg", ".svg")):
            dir_path = project_root / folder
            if not dir_path.exists():
                continue
            for path in dir_path.glob("frame_*" + suffix):
                idx = self._parse_frame_index(path.name)
                if idx > max_idx:
                    max_idx = idx
        return max_idx

    @staticmethod
    def _parse_frame_index(name: str) -> int:
        try:
            base = name.split(".")[0]
            parts = base.split("_")
            if len(parts) < 2:
                return 0
            return int(parts[-1])
        except ValueError:
            return 0

    def _on_play_tick(self) -> None:
        if not self._play_active:
            return
        project = (self._general_panel.edit_project.text() or "").strip()
        if not project:
            self.stop_play()
            return
        self.show_frame_preview(project, self._play_frame, log_preview=False)
        self._pipeline_panel.spin_frame.setValue(self._play_frame)
        self._play_frame += 1
        if self._play_frame > self._play_end_frame:
            if self._pipeline_panel.check_loop.isChecked():
                self._play_frame = 1
            else:
                self.stop_play()

    def on_palette_changed(self, _index: int) -> None:
        try:
            self.show_current_frame()
        except Exception:
            pass

    def show_frame_preview(
        self,
        project: str,
        ui_frame: int,
        log_preview: bool = True,
    ) -> None:
        project_root = self._projects_root / project
        paths = self._preview_service.frame_paths(project_root, ui_frame)
        self._show_frame_paths(paths)
        self._clear_arcade_preview_if_needed()
        if log_preview and paths.png is not None:
            self._log(f"[Preview] PNG: {paths.png}")
        if log_preview and paths.bmp is not None:
            self._log(f"[Preview] BMP: {paths.bmp}")
        if log_preview and paths.svg is not None:
            self._log(f"[Preview] SVG: {paths.svg}")

        ilda_path = self._resolve_ilda_path(project_root, project)
        if ilda_path is not None:
            preview_dir = project_root / "preview"
            preview_dir.mkdir(parents=True, exist_ok=True)
            out_png = preview_dir / f"ilda_preview_{ui_frame:04d}.png"
            try:
                self._render_ilda_preview(ilda_path, out_png, ui_frame)
                if log_preview:
                    self._log(f"[Preview] ILDA frame {ui_frame} : {out_png}")
            except Exception as exc:
                if log_preview:
                    self._log(
                        f"[Preview] Failed to generate ILDA preview for frame {ui_frame}: {exc}"
                    )
        else:
            self._pipeline_panel.preview_ilda.clear()
            if log_preview:
                self._log("[Preview] No ILDA file found for this frame.")

    def _clear_arcade_preview_if_needed(self) -> None:
        if not self._is_arcade_mode():
            try:
                self._pipeline_panel.clear_arcade_preview()
            except Exception:
                pass

    def _is_arcade_mode(self) -> bool:
        mode = self._pipeline_panel.combo_ilda_mode.currentData() or "classic"
        return str(mode).lower() == "arcade"

    def _show_frame_paths(self, paths: FramePreviewPaths) -> None:
        if paths.png is not None:
            self._pipeline_panel.preview_png.show_image(str(paths.png))
        else:
            self._pipeline_panel.preview_png.clear()
        if paths.bmp is not None:
            self._pipeline_panel.preview_bmp.show_image(str(paths.bmp))
        else:
            self._pipeline_panel.preview_bmp.clear()
        if paths.svg is not None:
            self._pipeline_panel.preview_svg.show_svg(str(paths.svg))
        else:
            self._pipeline_panel.preview_svg.clear()
        if self._is_arcade_mode():
            if paths.arcade is not None:
                self._pipeline_panel.show_arcade_preview(str(paths.arcade))
            else:
                self._pipeline_panel.clear_arcade_preview()

    def _render_ilda_preview(self, ilda_path: Path, out_png: Path, ui_frame: int) -> None:
        self._preview_service.ensure_ilda_preview(
            ilda_path,
            out_png,
            frame_index_0based=max(0, ui_frame - 1),
            palette_name=self._get_palette_name(),
        )
        self._pipeline_panel.preview_ilda.show_image(str(out_png))

    def update_ilda_preview(self, project: str) -> None:
        project_root = self._projects_root / project
        svg_dir = project_root / "svg"
        svg_files = sorted(svg_dir.glob("frame_*.svg"))
        if svg_files:
            self._pipeline_panel.preview_svg.show_svg(str(svg_files[0]))
            self._log(f"[Preview] SVG: {svg_files[0]}")
        else:
            self._pipeline_panel.preview_svg.clear()

        preview_dir = project_root / "preview"
        preview_dir.mkdir(parents=True, exist_ok=True)

        ilda_path = self._resolve_ilda_path(project_root, project)
        if ilda_path is None:
            self._pipeline_panel.preview_ilda.clear()
            return
        out_png = preview_dir / "ilda_preview.png"
        try:
            self._render_ilda_preview(ilda_path, out_png, 1)
            self._log(f"[Preview] ILDA: {out_png}")
        except Exception as exc:
            self._log(f"[Preview] Failed to generate ILDA preview: {exc}")

    def show_progress_frame(self, step_name: str, path: str) -> None:
        if step_name == "ffmpeg":
            self._pipeline_panel.preview_png.show_image(path)
        elif step_name == "bitmap":
            self._pipeline_panel.preview_bmp.show_image(path)
        elif step_name == "potrace":
            self._pipeline_panel.preview_svg.show_svg(path)
        elif step_name == "ilda":
            self._pipeline_panel.preview_ilda.show_image(path)
        elif step_name == "arcade_lines":
            self._pipeline_panel.show_arcade_preview(path)

    def _resolve_ilda_path(self, project_root: Path, project: str) -> Path | None:
        candidates = [
            project_root / f"{project}.ild",
            project_root / "ilda" / f"{project}.ild",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _get_palette_name(self) -> str:
        try:
            combo = getattr(self._pipeline_panel, "combo_ilda_palette", None)
            if combo is not None:
                key = combo.currentData()
                if isinstance(key, str) and key.strip():
                    return key.strip()
                txt = combo.currentText()
                if isinstance(txt, str) and txt.strip():
                    return txt.strip()
        except Exception:
            pass

        return os.getenv("ILDA_PREVIEW_PALETTE", "ilda64")
