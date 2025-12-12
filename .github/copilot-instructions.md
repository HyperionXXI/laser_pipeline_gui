# Copilot / AI agent instructions for laser_pipeline_gui

Short guide to get an AI-coding agent productive in this repository.

1) Big picture
- Purpose: GUI-driven pipeline that converts a video → PNG frames → BMP → SVG → ILDA.
- Main subsystems:
  - `core/` : pipeline steps and low-level ILDA handling (`core/step_*.py`, `core/ilda_writer.py`, `core/step_ilda.py`).
  - `core/pipeline/` : thin pipeline wrappers that expose StepResult/FrameProgress and callback patterns.
  - `gui/` : PySide6-based GUI (`gui/main_window.py`, `gui/pipeline_controller.py`, `gui/preview_widgets.py`).
  - `projects/` : per-project working directories created under `PROJECTS_ROOT` (see `core/config.py`).

2) Key workflows & commands
- Run the GUI (launches PySide6 app):
  `python gui_main.py`
- Run tests (uses pytest; tests live in `tests/`):
  `python -m pytest -q`
- Tools required on the system: `ffmpeg`, `magick` (ImageMagick), `potrace`. Paths can be overridden via env vars:
  - `LPIP_FFMPEG`, `LPIP_MAGICK`, `LPIP_POTRACE` (see `core/config.py`).

3) Project layout and conventions
- Project root for outputs: `PROJECTS_ROOT` (from `core/config.py`). Typical per-project subfolders:
  - `projects/<project>/frames/frame_XXXX.png`
  - `projects/<project>/bmp/frame_XXXX.bmp`
  - `projects/<project>/svg/frame_XXXX.svg`
  - `projects/<project>/ilda/<project>.ild`
- Frame file names use `frame_XXXX` zero-padded format; many helpers assume this pattern.
- Pipeline step result and progress types:
  - `core.pipeline.base.StepResult` (success/message/output_dir)
  - `core.pipeline.base.FrameProgress` (step_name, frame_index, total_frames, frame_path)
  - Steps accept `progress_cb` and `cancel_cb` callbacks (see `core/pipeline/ilda_step.py` for example).

4) Important implementation notes (do not change lightly)
- `core/ilda_writer.py` expects ILDA coordinates already scaled into [-32768, +32767]. When generating points, clamp/normalize to that range.
- `export_project_to_ilda(...)` (in `core/step_ilda.py` / `core/step_ilda` module) is the bridge between SVG parsing and `ilda_writer`. The SVG→ILDA conversion is experimental — prefer small, testable changes.
- GUI triggers pipeline actions via `PipelineController` (signals/slots + QThread/Worker model). Keep long-running work in worker threads and report progress through `FrameProgress` objects.

5) Where to make changes for common tasks
- Add/modify a pipeline step: edit `core/step_{ffmpeg,bitmap,potrace,ilda}.py` and the corresponding wrapper in `core/pipeline/`.
- Add a preview or GUI control: edit `gui/preview_widgets.py` or `gui/main_window.py`. Respect signal/slot patterns used by `PipelineController`.
- Add a low-level ILDA feature: edit `core/ilda_writer.py`. Existing functions to reference:
  - `write_ilda_file(path, frames)` — writes an iterable of `IldaFrame`.
  - `write_test_square(path)` — creates a minimal test ILDA file used by unit tests.

6) Quick code examples
- Generate an ILDA file programmatically (non-GUI):
```py
from core.pipeline.ilda_step import run_ilda_step
res = run_ilda_step("projet_demo", "classic")
print(res.message)
```
- Create a test square ILDA file (used by tests):
```py
from core.ilda_writer import write_test_square
write_test_square("projects/projet_demo/ilda/projet_demo.ild")
```

7) Tests and debugging
- Unit tests for ILDA writer live in `tests/` (e.g. `test_ilda_square.py`). Use `-q` to reduce verbosity.
- When changing external-tool invocations, prefer to mock/replace the external call in tests or set env vars `LPIP_*` to point to test binaries.

8) Agent-specific tips (how an AI assistant should act)
- Prefer small, localized edits that preserve public APIs and existing behavior.
- When modifying pipeline behavior, update or add a unit test in `tests/` that demonstrates the change (e.g. using `write_test_square`).
- If adding features that require external tools, document required env vars in `core/config.py` and add guidance here.
- When unsure about visual/preview behavior, run the GUI locally with `python gui_main.py` and use the `projet_demo` sample in `projects/` for manual verification.

If any part is unclear or you want more examples (e.g. a walkthrough editing `core/step_potrace.py`), tell me which area to expand. 
