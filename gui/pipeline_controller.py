from __future__ import annotations

import inspect
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from core.config import PROJECTS_ROOT
from core.ffmpeg_extract import extract_frames
from core.bitmap_convert import convert_project_frames_to_bmp
from core.potrace_vectorize import bitmap_to_svg_folder
from core.ilda_export import export_project_to_ilda
from core.pipeline.base import FrameProgress


@dataclass(frozen=True)
class StepResult:
    success: bool
    message: str = ""
    output_path: Optional[Path] = None


class PipelineController(QObject):
    """Orchestration des steps dans un thread python.

    Objectif:
    - garder la GUI réactive
    - envoyer des signaux cohérents: step_started/finished/error/progress
    - supporter l'annulation (au moins *entre* les frames / steps)
    """

    step_started = Signal(str)
    step_finished = Signal(str, object)  # StepResult
    step_error = Signal(str, str)
    step_progress = Signal(str, object)  # FrameProgress

    def __init__(self, parent: Optional[QObject] = None, log_fn: Optional[Callable[[str], None]] = None) -> None:
        super().__init__(parent)
        self._log = log_fn
        self._thread: Optional[threading.Thread] = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    # ------------- public API -------------
    def cancel_current_step(self) -> None:
        self._cancel.set()

    def start_ffmpeg(self, video_path: str, project: str, fps: int) -> None:
        self._start_background("ffmpeg", lambda: self._run_ffmpeg(video_path, project, fps))

    def start_bitmap(self, project: str, threshold: int, use_thinning: bool, max_frames: Optional[int]) -> None:
        self._start_background("bitmap", lambda: self._run_bitmap(project, threshold, use_thinning, max_frames))

    def start_potrace(self, project: str) -> None:
        self._start_background("potrace", lambda: self._run_potrace(project))

    def start_ilda(
        self,
        project: str,
        *,
        ilda_mode: str = "classic",
        fit_axis: str = "max",
        fill_ratio: float = 0.95,
        min_rel_size: float = 0.01,
        max_frames: Optional[int] = None,
    ) -> None:
        self._start_background(
            "ilda",
            lambda: self._run_ilda(
                project,
                ilda_mode=ilda_mode,
                fit_axis=fit_axis,
                fill_ratio=fill_ratio,
                min_rel_size=min_rel_size,
                max_frames=max_frames,
            ),
        )

    def start_full_pipeline(
        self,
        *,
        video_path: str,
        project: str,
        fps: int,
        threshold: int,
        use_thinning: bool,
        max_frames: Optional[int],
        ilda_mode: str = "classic",
        fit_axis: str = "max",
        fill_ratio: float = 0.95,
        min_rel_size: float = 0.01,
    ) -> None:
        def job() -> StepResult:
            return self._run_full_pipeline(
                video_path=video_path,
                project=project,
                fps=fps,
                threshold=threshold,
                use_thinning=use_thinning,
                max_frames=max_frames,
                ilda_mode=ilda_mode,
                fit_axis=fit_axis,
                fill_ratio=fill_ratio,
                min_rel_size=min_rel_size,
            )

        self._start_background("full_pipeline", job)

    # ------------- internals -------------
    def _start_background(self, step_name: str, fn: Callable[[], StepResult]) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                self.step_error.emit(step_name, "Une tâche est déjà en cours.")
                return
            self._cancel.clear()

            def runner() -> None:
                try:
                    self.step_started.emit(step_name)
                    res = fn()
                    if self._cancel.is_set():
                        self.step_error.emit(step_name, "Annulé.")
                        return
                    self.step_finished.emit(step_name, res)
                except Exception as e:
                    self.step_error.emit(step_name, str(e))

            self._thread = threading.Thread(target=runner, daemon=True)
            self._thread.start()

    def _emit_frame(self, step_name: str, frame_index: int, total_frames: Optional[int], frame_path: Optional[Path]) -> None:
        fp = FrameProgress(frame_index=frame_index, total_frames=total_frames, frame_path=frame_path)
        self.step_progress.emit(step_name, fp)

    def _project_root(self, project: str) -> Path:
        return PROJECTS_ROOT / project

    def _check_cancel(self) -> bool:
        return self._cancel.is_set()

    def _log_debug(self, msg: str) -> None:
        if self._log:
            self._log(msg)

    # ------------- step implementations -------------
    def _run_ffmpeg(self, video_path: str, project: str, fps: int) -> StepResult:
        if self._check_cancel():
            return StepResult(False, "Annulé.")
        extract_frames(video_path=video_path, project_name=project, fps=fps)
        # pousser au moins une preview (frame_0001.png si présent)
        frame1 = self._project_root(project) / "frames" / "frame_0001.png"
        if frame1.exists():
            self._emit_frame("ffmpeg", 1, None, frame1)
        return StepResult(True, f"FFmpeg OK -> {project}")

    def _run_bitmap(self, project: str, threshold: int, use_thinning: bool, max_frames: Optional[int]) -> StepResult:
        def cb(i: int, total: int, p: Path) -> None:
            self._emit_frame("bitmap", i, total, p)

        out_dir = convert_project_frames_to_bmp(
            project_name=project,
            threshold=threshold,
            use_thinning=use_thinning,
            max_frames=max_frames,
            frame_callback=cb,
            cancel_cb=self._check_cancel,
        )
        return StepResult(True, f"BMP OK -> {out_dir}")

    def _run_potrace(self, project: str) -> StepResult:
        root = self._project_root(project)
        bmp_dir = root / "bmp"
        svg_dir = root / "svg"

        def cb(i: int, total: int, p: Path) -> None:
            self._emit_frame("potrace", i, total, p)

        out_dir = bitmap_to_svg_folder(
            bmp_dir=bmp_dir,
            svg_dir=svg_dir,
            frame_callback=cb,
            cancel_cb=self._check_cancel,
        )
        return StepResult(True, f"Potrace OK -> {out_dir}")

    def _run_ilda(
        self,
        project: str,
        *,
        ilda_mode: str,
        fit_axis: str,
        fill_ratio: float,
        min_rel_size: float,
        max_frames: Optional[int],
    ) -> StepResult:
        def progress(i: int, total: int) -> None:
            # pas forcément un fichier, mais on peut pointer vers le SVG correspondant si dispo
            svg = self._project_root(project) / "svg" / f"frame_{i:04d}.svg"
            self._emit_frame("ilda", i, total, svg if svg.exists() else None)

        out = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            mode=ilda_mode,
            check_cancel=self._check_cancel,
            report_progress=progress,
        )
        return StepResult(True, f"ILDA OK -> {out}", output_path=out)

    def _try_import_arcade_step(self):
        """Importe le step OpenCV (Arcade v2) s'il existe dans le projet."""
        candidates = [
            "core.pipeline.arcade_lines_step",
            "core.pipeline.arcade_step",
            "core.arcade_lines_step",
        ]
        for modname in candidates:
            try:
                mod = __import__(modname, fromlist=["*"])
            except Exception:
                continue
            for fn_name in ("run_arcade_lines_step", "arcade_lines_step", "run_step"):
                fn = getattr(mod, fn_name, None)
                if callable(fn):
                    return fn
        return None

    def _run_arcade_lines(self, project: str, max_frames: Optional[int]) -> StepResult:
        fn = self._try_import_arcade_step()
        if fn is None:
            raise RuntimeError(
                "Arcade mode sélectionné mais le step OpenCV 'arcade_lines_step' est introuvable.\n"
                "Vérifie que core/pipeline/arcade_lines_step.py existe et expose run_arcade_lines_step()."
            )

        def cb(i: int, total: int, p: Path) -> None:
            self._emit_frame("arcade_lines", i, total, p)

        # Appel flexible (on filtre les kwargs selon la signature)
        kwargs = {
            "project_name": project,
            "project": project,
            "max_frames": max_frames,
            "frame_callback": cb,
            "cancel_cb": self._check_cancel,
            "check_cancel": self._check_cancel,
            "report_progress": cb,
        }
        sig = inspect.signature(fn)
        call_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        out = fn(**call_kwargs)
        return StepResult(True, f"Arcade lines OK -> {out}")

    def _run_full_pipeline(
        self,
        *,
        video_path: str,
        project: str,
        fps: int,
        threshold: int,
        use_thinning: bool,
        max_frames: Optional[int],
        ilda_mode: str,
        fit_axis: str,
        fill_ratio: float,
        min_rel_size: float,
    ) -> StepResult:
        # Maintenir busy via 'full_pipeline', mais publier les previews via step_progress avec le step courant.
        # FFmpeg
        extract_frames(video_path=video_path, project_name=project, fps=fps)

        if self._check_cancel():
            return StepResult(False, "Annulé.")

        # Classic pipeline
        if ilda_mode != "arcade":
            def cb_bmp(i: int, total: int, p: Path) -> None:
                self._emit_frame("bitmap", i, total, p)

            convert_project_frames_to_bmp(
                project_name=project,
                threshold=threshold,
                use_thinning=use_thinning,
                max_frames=max_frames,
                frame_callback=cb_bmp,
                cancel_cb=self._check_cancel,
            )

            if self._check_cancel():
                return StepResult(False, "Annulé.")

            root = self._project_root(project)
            bmp_dir = root / "bmp"
            svg_dir = root / "svg"

            def cb_svg(i: int, total: int, p: Path) -> None:
                self._emit_frame("potrace", i, total, p)

            bitmap_to_svg_folder(
                bmp_dir=bmp_dir,
                svg_dir=svg_dir,
                frame_callback=cb_svg,
                cancel_cb=self._check_cancel,
            )

            if self._check_cancel():
                return StepResult(False, "Annulé.")

        # Arcade pipeline: OpenCV -> SVG (avec data-rgb) -> ILDA (truecolor)
        else:
            self._run_arcade_lines(project, max_frames=max_frames)

            if self._check_cancel():
                return StepResult(False, "Annulé.")

        # ILDA export (classic ou arcade)
        def progress(i: int, total: int) -> None:
            svg = self._project_root(project) / "svg" / f"frame_{i:04d}.svg"
            self._emit_frame("ilda", i, total, svg if svg.exists() else None)

        out = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            mode=ilda_mode,
            check_cancel=self._check_cancel,
            report_progress=progress,
        )

        return StepResult(True, f"{ilda_mode} OK -> {out}", output_path=out)
