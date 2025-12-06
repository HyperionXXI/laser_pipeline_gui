# gui/pipeline_controller.py
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.pipeline.base import FrameProgress, StepResult
from core.pipeline.ffmpeg_step import run_ffmpeg_step
from core.pipeline.bitmap_step import run_bitmap_step
from core.pipeline.potrace_step import run_potrace_step
from core.pipeline.ilda_step import run_ilda_step

LogFn = Callable[[str], None]


class _StepWorker(QObject):
    """
    Worker générique utilisé en interne par PipelineController.
    """
    finished = Signal(object)   # StepResult
    error = Signal(str)
    progress = Signal(object)   # FrameProgress

    def __init__(self, step_func: Callable[..., StepResult], *args, **kwargs) -> None:
        super().__init__()
        self._step_func = step_func
        self._args = args
        self._kwargs = kwargs
        self._cancel_requested = False

    @Slot()
    def run(self) -> None:
        try:
            def cancel_cb() -> bool:
                return self._cancel_requested

            def progress_cb(fp: FrameProgress) -> None:
                self.progress.emit(fp)

            result = self._step_func(
                *self._args,
                progress_cb=progress_cb,
                cancel_cb=cancel_cb,
                **self._kwargs,
            )
        except Exception as e:
            self.error.emit(str(e))
        else:
            self.finished.emit(result)

    def cancel(self) -> None:
        self._cancel_requested = True


class PipelineController(QObject):
    """
    Contrôleur de pipeline : encapsule ffmpeg, bitmap, potrace, etc.
    """

    step_started = Signal(str)          # "ffmpeg", "bitmap", ...
    step_finished = Signal(str, object) # step_name, StepResult
    step_error = Signal(str, str)       # step_name, message
    step_progress = Signal(str, object) # step_name, FrameProgress

    def __init__(self, parent: Optional[QObject] = None,
                 log_fn: Optional[LogFn] = None) -> None:
        super().__init__(parent)
        self._log = log_fn or (lambda msg: None)

        self._thread: Optional[QThread] = None
        self._worker: Optional[_StepWorker] = None
        self._current_step: Optional[str] = None

    # ------------------------------------------------------------------
    # Gestion générique d'un step
    # ------------------------------------------------------------------

    def _start_step(self,
                    step_name: str,
                    step_func: Callable[..., StepResult],
                    *args, **kwargs) -> None:
        if self._thread is not None:
            self._log(f"[Pipeline] Un step est déjà en cours ({self._current_step}).")
            return

        self._log(f"[Pipeline] Démarrage step '{step_name}'...")
        self._current_step = step_name

        thread = QThread(self)
        worker = _StepWorker(step_func, *args, **kwargs)
        worker.moveToThread(thread)

        def cleanup() -> None:
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()
            self._thread = None
            self._worker = None
            self._current_step = None

        def on_finished(result: StepResult) -> None:
            self._log(f"[Pipeline] Step '{step_name}' terminé.")
            self.step_finished.emit(step_name, result)
            cleanup()

        def on_error(message: str) -> None:
            self._log(f"[Pipeline] ERREUR dans step '{step_name}' : {message}")
            self.step_error.emit(step_name, message)
            cleanup()

        def on_progress(fp: FrameProgress) -> None:
            self.step_progress.emit(step_name, fp)

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(on_progress)
        thread.started.connect(worker.run)

        self._thread = thread
        self._worker = worker

        self.step_started.emit(step_name)
        thread.start()

    # ------------------------------------------------------------------
    # API publique pour la GUI
    # ------------------------------------------------------------------

    def start_ffmpeg(self, video_path: str, project: str, fps: int) -> None:
        self._start_step("ffmpeg", run_ffmpeg_step, video_path, project, fps)

    def start_bitmap(self,
                     project: str,
                     threshold: int,
                     use_thinning: bool,
                     max_frames: Optional[int]) -> None:
        self._start_step(
            "bitmap",
            run_bitmap_step,
            project,
            threshold,
            use_thinning,
            max_frames,
        )

    def start_potrace(self, project: str) -> None:
        self._start_step("potrace", run_potrace_step, project)
        

    def start_ilda(
        self,
        project: str,
        fit_axis: str = "max",
        fill_ratio: float = 0.95,
        min_rel_size: float = 0.01,
    ) -> None:
        """
        Lance l'export ILDA pour un projet.

        - project : nom du projet (dossier sous PROJECTS_ROOT)
        - fit_axis : "max", "x", "y" (voir step_ilda)
        - fill_ratio : 0..1
        - min_rel_size : filtre de chemins parasites
        """
        self._start_step(
            step_name="ilda",
            step_func=run_ilda_step,
            project=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
        )


    def cancel_current_step(self) -> None:
        if self._worker is not None:
            self._log("[Pipeline] Annulation demandée…")
            self._worker.cancel()
