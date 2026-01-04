# core/pipeline/ilda_step.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from core.config import PROJECTS_ROOT
from core.ilda_export import export_project_to_ilda
from core.pipeline.base import StepResult, FrameProgress, ProgressCallback, CancelCallback


def run_ilda_step(
    project: str,
    fit_axis: str = "max",
    fill_ratio: float = 0.95,
    min_rel_size: float = 0.01,
    mode: str = "classic",
    swap_rb: bool = False,
    *,
    progress_cb: Optional[ProgressCallback] = None,
    cancel_cb: Optional[CancelCallback] = None,
    # compat: callers may pass max_frames even though export currently ignores it
    max_frames: Optional[int] = None,
) -> StepResult:
    step_name = "ilda"

    def count_frames(project_name: str, mode_key: str) -> Optional[int]:
        try:
            mode_norm = (mode_key or "classic").lower()
            project_root = PROJECTS_ROOT / project_name
            if mode_norm == "arcade":
                manifest_path = project_root / "bmp" / "_layers_manifest.json"
                if not manifest_path.exists():
                    return None
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                frames = manifest.get("frames", [])
                return len(frames)

            svg_dir = project_root / "svg"
            svg_files = sorted(svg_dir.glob("frame_*.svg"))
            return len(svg_files)
        except Exception:
            return None

    def check_cancel() -> bool:
        return bool(cancel_cb and cancel_cb())

    def report_progress(frame_index: int, total_frames: int) -> None:
        if progress_cb:
            progress_cb(
                FrameProgress(
                    step_name=step_name,
                    message=f"Frame {frame_index + 1}/{total_frames}",
                    frame_index=frame_index + 1,
                    total_frames=total_frames,
                    frame_path=None,
                )
            )

    try:
        out_path: Path = export_project_to_ilda(
            project_name=project,
            fit_axis=fit_axis,
            fill_ratio=fill_ratio,
            min_rel_size=min_rel_size,
            mode=mode,
            swap_rb=swap_rb,
            check_cancel=check_cancel,
            report_progress=report_progress,
        )

        frame_count = count_frames(project, mode)
        if frame_count is None:
            msg = f"ILDA computed: {out_path.name} (mode={mode})"
        else:
            msg = f"ILDA computed: {out_path.name} (mode={mode}, frames={frame_count})"

        return StepResult(
            success=True,
            message=msg,
            output_dir=out_path.parent,
        )

    except Exception as exc:
        return StepResult(
            success=False,
            message=f"ILDA computation error: {exc}",
            output_dir=None,
        )
