# gui/pipeline_controller.py
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from core.pipeline.base import FrameProgress, StepResult
from core.pipeline.bitmap_step import run_bitmap_step

class StepWorker(QObject):
    """
    Worker générique qui exécute une fonction d'étape dans un QThread.

    La fonction est appelée avec les callbacks :
        - on_progress(FrameProgress)
        - check_cancel() -> bool
    si elle accepte ces arguments. Sinon on retombe sur un appel simple.
    """
    finished = Signal(object)   # StepResult
    error = Signal(str)
    progress = Signal(object)   # FrameProgress

    def __init__(self, step_func: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self._step_func = step_func
        self._args = args
        self._kwargs = kwargs
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _check_cancel(self) -> bool:
        return self._cancelled

    def _on_progress(self, evt: FrameProgress) -> None:
        self.progress.emit(evt)

    @Slot()
    def run(self):
        try:
            # Tentative avec callbacks génériques
            try:
                result = self._step_func(
                    *self._args,
                    on_progress=self._on_progress,
                    check_cancel=self._check_cancel,
                    **self._kwargs,
                )
            except TypeError:
                # La fonction ne veut pas (encore) des callbacks -> appel simple
                result = self._step_func(*self._args, **self._kwargs)

        except Exception as e:
            self.error.emit(str(e))
        else:
            self.finished.emit(result)


class PipelineController(QObject):
    """
    Contrôleur centralisé du pipeline.
    Gère un seul step à la fois (simplicité) :
      - création / destruction du QThread
      - signaux haut-niveau vers le GUI
    """

    step_started = Signal(str)          # nom de l'étape
    step_progress = Signal(object)      # FrameProgress
    step_finished = Signal(object)      # StepResult
    step_error = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: StepWorker | None = None
        self._current_step: str | None = None

    # ---------- gestion interne ----------

    def _cleanup(self):
        thread = self._thread
        worker = self._worker
        self._thread = None
        self._worker = None
        self._current_step = None

        if thread is not None:
            thread.quit()
            thread.wait()
            thread.deleteLater()
        if worker is not None:
            worker.deleteLater()

    def _start_step(self, step_name: str, func: Callable[..., Any], *args, **kwargs):
        """
        Lance une étape dans un worker dédié.
        Pour l'instant, on refuse de lancer une étape si une autre tourne encore.
        """
        if self._thread is not None:
            # On pourrait lever une exception ou émettre une erreur,
            # pour l'instant on ignore simplement.
            self.step_error.emit(
                f"Impossible de lancer l'étape '{step_name}' : une autre étape est déjà en cours."
            )
            return

        self._current_step = step_name
        self.step_started.emit(step_name)

        thread = QThread(self)
        worker = StepWorker(func, *args, **kwargs)
        worker.moveToThread(thread)

        def on_finished(result: StepResult):
            self.step_finished.emit(result)
            self._cleanup()

        def on_error(message: str):
            self.step_error.emit(message)
            self._cleanup()

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.progress.connect(self.step_progress)
        thread.started.connect(worker.run)

        self._thread = thread
        self._worker = worker
        thread.start()

    # ---------- API publique pour le GUI ----------

    def start_ffmpeg(self, video_path: Path, project_name: str, fps: int):
        """
        Lance l'étape FFmpeg. Les paramètres spécifiques lui sont passés ici,
        les callbacks génériques sont gérés par StepWorker.
        """
        from core.pipeline.ffmpeg_step import run_ffmpeg_step
        self._start_step("ffmpeg", run_ffmpeg_step, video_path, project_name, fps)

    def cancel_current(self):
        """Demande l'annulation de l'étape actuelle (si supportée)."""
        if self._worker is not None:
            self._worker.cancel()

    # --- Étape BITMAP -------------------------------------------------

    def start_bitmap(
        self,
        project_name: str,
        threshold: int,
        use_thinning: bool,
        max_frames: int | None,
    ) -> None:
        """
        Lance l'étape Bitmap dans un Worker (PNG -> BMP).
        """
        def job(on_progress, check_cancel):
            return run_bitmap_step(
                project_name=project_name,
                threshold=threshold,
                use_thinning=use_thinning,
                max_frames=max_frames,
                on_progress=on_progress,
                check_cancel=check_cancel,
            )

        self._start_step_generic("bitmap", job)

