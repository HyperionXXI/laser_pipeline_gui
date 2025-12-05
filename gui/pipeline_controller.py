from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.pipeline.ffmpeg_step import run_ffmpeg_step
from core.pipeline.bitmap_step import run_bitmap_step
from core.pipeline.potrace_step import run_potrace_step
from core.pipeline.base import FrameProgress, StepResult

# Type alias: fonction de log appelée par le contrôleur
LogFn = Callable[[str], None]


class _StepWorker(QObject):
    """
    Worker générique utilisé en interne par PipelineController.

    Il appelle une fonction de step (run_ffmpeg_step, run_bitmap_step, ...)
    en lui passant des callbacks de progression / annulation.
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
        except Exception as e:  # garde-fou
            self.error.emit(str(e))
        else:
            self.finished.emit(result)

    def cancel(self) -> None:
        self._cancel_requested = True


class PipelineController(QObject):
    """
    Contrôleur de pipeline : encapsule la logique des 4 étapes
    (FFmpeg, Bitmap, Potrace, ILDA) et gère un seul step à la fois.

    La GUI n'a pas à manipuler les threads directement : elle appelle
    start_ffmpeg(...) / start_bitmap(...), et se connecte aux signaux.
    """

    # signaux exposés à la GUI
    step_started = Signal(str)               # ex: "ffmpeg", "bitmap"
    step_finished = Signal(str, object)      # step_name, StepResult
    step_error = Signal(str, str)            # step_name, message
    step_progress = Signal(str, object)      # step_name, FrameProgress

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

    def _start_step(self, step_name: str,
                    step_func: Callable[..., StepResult],
                    *args, **kwargs) -> None:
        """
        Démarre un step dans un QThread.

        - step_name : étiquette pour les signaux/logs ("ffmpeg", "bitmap", ...)
        - step_func : fonction comme run_ffmpeg_step(...)
        - *args / **kwargs : paramètres passés au step_func
        """
        # Si un step est déjà en cours, on refuse d'en lancer un autre
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

    def cancel_current_step(self) -> None:
        """
        Demande l'annulation du step courant (si possible).
        """
        if self._worker is not None:
            self._log("[Pipeline] Annulation demandée.")
            self._worker.cancel()

    # ------------------------------------------------------------------
    # API spécifique aux 2 étapes déjà intégrées
    # ------------------------------------------------------------------

    def start_ffmpeg(self, video_path: str, project: str, fps: int) -> None:
        self._start_step("ffmpeg", run_ffmpeg_step, video_path, project, fps=fps)

    def start_bitmap(self, project: str,
                     threshold: int,
                     use_thinning: bool,
                     max_frames: int | None) -> None:
        self._start_step(
            "bitmap",
            run_bitmap_step,
            project,
            threshold=threshold,
            use_thinning=use_thinning,
            max_frames=max_frames,
        )

    def start_potrace(self, project_name: str) -> None:
        """
        Lance la vectorisation Potrace (BMP -> SVG) dans un QThread.
        """
        self._start_step("potrace", run_potrace_step, project_name)

    # Les étapes Potrace et ILDA pourront être ajoutées dans le même style plus tard.
