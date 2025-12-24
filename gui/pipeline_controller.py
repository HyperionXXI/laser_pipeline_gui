# gui/pipeline_controller.py
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtCore import QObject, Signal

from core.pipeline.base import FrameProgress, StepResult
from core.pipeline.bitmap_step import run_bitmap_step
from core.pipeline.ffmpeg_step import run_ffmpeg_step
from core.pipeline.full_pipeline_step import run_full_pipeline_step
from core.pipeline.ilda_step import run_ilda_step
from core.pipeline.potrace_step import run_potrace_step


@dataclass(frozen=True)
class _Task:
    step_name: str
    fn: Callable[[], StepResult]


class PipelineController(QObject):
    step_started = Signal(str)
    step_finished = Signal(str, object)
    step_error = Signal(str, str)
    step_progress = Signal(str, object)

    def __init__(
        self,
        *,
        parent: Optional[QObject] = None,
        log_fn: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._log_fn = log_fn

        self._thread: Optional[threading.Thread] = None
        self._cancel_evt: Optional[threading.Event] = None
        self._announced_substeps: set[str] = set()

    def cancel_current_step(self) -> None:
        if self._cancel_evt is None:
            return
        self._cancel_evt.set()
        self._log("[Pipeline] Annulation demandée…")

    def start_ffmpeg(self, video_path: str, project: str, fps: int) -> None:
        self._start_background(
            _Task(
                step_name="ffmpeg",
                fn=lambda: run_ffmpeg_step(
                    video_path,
                    project,
                    fps,
                    progress_cb=self._make_progress_cb(top_step="ffmpeg"),
                    cancel_cb=self._make_cancel_cb(),
                ),
            )
        )

    def start_bitmap(
        self,
        project: str,
        threshold: int,
        use_thinning: bool,
        max_frames: Optional[int],
    ) -> None:
        # Step 2 UI = "PNG -> BMP (seuil)" => mode classic
        self._start_background(
            _Task(
                step_name="bitmap",
                fn=lambda: run_bitmap_step(
                    project,
                    threshold,
                    use_thinning,
                    max_frames,
                    progress_cb=self._make_progress_cb(top_step="bitmap"),
                    cancel_cb=self._make_cancel_cb(),
                    mode="classic",
                ),
            )
        )

    def start_potrace(self, project: str) -> None:
        self._start_background(
            _Task(
                step_name="potrace",
                fn=lambda: run_potrace_step(
                    project,
                    progress_cb=self._make_progress_cb(top_step="potrace"),
                    cancel_cb=self._make_cancel_cb(),
                ),
            )
        )

    def start_ilda(
        self,
        project: str,
        *,
        ilda_mode: str = "classic",
        fit_axis: str = "max",
        fill_ratio: float = 0.95,
        min_rel_size: float = 0.01,
    ) -> None:
        self._start_background(
            _Task(
                step_name="ilda",
                fn=lambda: run_ilda_step(
                    project,
                    fit_axis,
                    fill_ratio,
                    min_rel_size,
                    ilda_mode,
                    progress_cb=self._make_progress_cb(top_step="ilda"),
                    cancel_cb=self._make_cancel_cb(),
                ),
            )
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
    ) -> None:
        # UI: None (= toutes) -> 0
        max_frames_int = 0 if (max_frames is None) else int(max_frames)

        # Pour avancer: on force 60kpps en arcade (simple "User mode").
        arcade_params: Optional[dict[str, object]] = None
        if (ilda_mode or "").strip().lower() == "arcade":
            arcade_params = {
                "kpps": 60,
                "invert_y": True,       # IMPORTANT: coord image -> coord ILDA
                "sample_color": True,   # on veut des couleurs en arcade
            }

        self._start_background(
            _Task(
                step_name="full_pipeline",
                fn=lambda: run_full_pipeline_step(
                    video_path=video_path,
                    project=project,
                    fps=fps,
                    threshold=threshold,
                    use_thinning=use_thinning,
                    max_frames=max_frames_int,
                    ilda_mode=ilda_mode,
                    arcade_params=arcade_params,
                    progress_cb=self._make_progress_cb(top_step="full_pipeline"),
                    cancel_cb=self._make_cancel_cb(),
                ),
            )
        )

    # ---------------- Internals ----------------

    def _log(self, msg: str) -> None:
        if self._log_fn:
            self._log_fn(msg)

    def _make_cancel_cb(self) -> Callable[[], bool]:
        def _cb() -> bool:
            return bool(self._cancel_evt and self._cancel_evt.is_set())

        return _cb

    def _make_progress_cb(self, *, top_step: str) -> Callable[[FrameProgress], None]:
        def _cb(fp: FrameProgress) -> None:
            step_name = (fp.step_name or top_step).lower()

            if top_step == "full_pipeline":
                if step_name not in self._announced_substeps:
                    self._announced_substeps.add(step_name)
                    self._log(f"[Pipeline] Sous-step détecté: '{step_name}' (via progress)")
                    self.step_started.emit(step_name)

            self.step_progress.emit(step_name, fp)

        return _cb

    def _start_background(self, task: _Task) -> None:
        if self._thread and self._thread.is_alive():
            self._log("[Pipeline] Une tâche est déjà en cours (ignoring).")
            return

        self._cancel_evt = threading.Event()
        self._announced_substeps = set()

        self._log(f"[Pipeline] Démarrage step '{task.step_name}'...")
        self.step_started.emit(task.step_name)

        def _runner() -> None:
            try:
                res = task.fn()
                self._log(f"[Pipeline] Step '{task.step_name}' terminé.")
                self.step_finished.emit(task.step_name, res)
            except Exception as exc:  # noqa: BLE001
                self._log(f"[Pipeline] Step '{task.step_name}' erreur: {exc}")
                self.step_error.emit(task.step_name, str(exc))
            finally:
                self._cancel_evt = None
                self._thread = None

        self._thread = threading.Thread(target=_runner, daemon=True)
        self._thread.start()
