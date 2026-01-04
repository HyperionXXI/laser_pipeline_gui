# AGENTS.md - Codex playbook for laser_pipeline_gui (Python + PySide6)

## Language
- Default: respond in French.
- Keep code identifiers as-is (Python names, filenames, etc.).

## Mission
Help maintain and evolve `laser_pipeline_gui` without UI regressions.
Top priorities:
1) UI stability (no regressions).
2) Minimal, localized fixes (no big refactors unless explicitly requested).
3) Correct ILDA output (no dropped frames, blanking rules respected).

---

# A) Operating modes

## A1) Default mode: REVIEW -> PLAN -> IMPLEMENT (only if asked)
Unless the user explicitly says "implement", do:
1) REVIEW: repo map + risks + suspected root cause + impacted files.
2) PLAN: propose a small PR plan (2-3 PRs max) with definition of done.
3) IMPLEMENT: only after the user confirms.

## A2) Safe-by-default rules
- Never invent files/folders that do not exist.
- Never reintroduce old/deprecated layout (see Architecture lock).
- Never mix refactor + functional fix in the same commit.
- Never change external tool paths by guessing the user's machine.

---

# B) Architecture lock (DO NOT BREAK)
This repository has a canonical structure. Keep it.

## B1) Canonical tree (reference)
laser_pipeline_gui/
  core/
    config.py
    ffmpeg_extract.py
    bitmap_convert.py
    potrace_vectorize.py
    ilda_export.py
    ilda_writer.py
    ilda_profiles.py
    ilda_preview.py
    pipeline/
      __init__.py
      base.py
      ffmpeg_step.py
      bitmap_step.py
      potrace_step.py
      ilda_step.py
      arcade_lines_step.py
      full_pipeline_step.py
  gui/
    __init__.py
    main_window.py
    pipeline_controller.py
    preview_widgets.py
    models/
    services/
    ui/
  projects/
    <project_name>/
      frames/
      bmp/
      svg/
      preview/
      ilda/
      <project_name>.ild
      settings.json
  tests/
    test_ilda_minimal.py
    test_ilda_square.py
    test_ilda_square_v2.py
  docs/
    AGENTS.md
    GUI_VALIDATION.md
    STATE_ARCADE_V2.md
    images/
  gui_main.py
  README.md
  pyproject.toml
  .gitignore
  docs/legacy/
    _send_arcade_lines_step.py
    _send_full_pipeline_step.py
    _send_main_window.py
    _send_pipeline_controller.py

## B2) Strict anti-confusion rules
- DO NOT reintroduce: core/step_*.py
- DO NOT invent: core/steps/, pipeline/steps/, etc.
- Orchestrators ONLY in: core/pipeline/*_step.py
- Business logic ONLY in: core/*.py

## B3) Import rules
- core/pipeline/* may import core/*
- core/* must NOT import core/pipeline/*
- gui/* may import core/pipeline/* (not the inverse)

---

# C) UI stability contract (Definition of Done)
Before and after each significant change, run the GUI validation checklist
(`docs/GUI_VALIDATION.md`). Do not claim "fixed" if the checklist is not
satisfied.

Minimum checks (must stay green):
- `python -c "import gui.main_window as m; print('ok')"` prints ok
- `python gui_main.py` starts without exceptions
- F5 refresh previews even with no video selected
- Cancel really cancels and UI returns idle
- Classic mode: FFmpeg/Bitmap/Potrace/ILDA steps complete
- Arcade v2 mode: Run All completes; Bitmap/Potrace NOT executed; progress reaches 100%
- Event trace logs exist: STEP_STARTED / STEP_PROGRESS / STEP_FINISHED / STEP_ERROR

---

# D) Known high-risk traps (treat as blockers)

## D1) Progress callbacks signature mismatch (trap #1)
Typical regression: progress(percent) vs progress(done, total) mismatch.
Rule:
- Read core/pipeline/base.py and use ONE signature everywhere:
  - core/pipeline/*_step.py
  - gui/pipeline_controller.py
Before modifying any step/controller, search all progress invocations and harmonize.

## D2) ILDA blanking + "never drop frames" (trap #2)
- First point of each path must be blanked=True.
- Following points blanked=False.
- NEVER drop empty frames:
  - if a frame produces zero points, write one blanked point at (0,0)
Goal: keep same number of frames end-to-end.

## D3) "Cadre/rectangle parasite" (product priority)
Symptom: a frame-wide rectangle appears in LaserShowGen.
Most likely source: polarity / Potrace input (BMP->SVG stage).
Fix location:
- core/potrace_vectorize.py and/or core/pipeline/potrace_step.py
Do NOT patch it downstream in ilda_export.py or GUI.

## D4) ILDA preview support
core/ilda_preview.py supports formats 0/1/4/5 and embedded palettes (format 2).
Avoid reintroducing older preview limitations.

---

# E) Codex-specific workflows

## E1) Repo review template (output format)
When asked for a review, respond with:
1) Repo map: entry points, main modules, data flow, external tools.
2) Architecture assessment: what's clean, what's coupled, what's risky.
3) Top issues (max 5), each with:
   - Symptom
   - Root cause hypothesis
   - Files involved
   - Minimal fix approach
4) PR plan (2-3 PRs max), each with:
   - Goal
   - Exact files to change/create
   - Risks
   - Validation steps (GUI_VALIDATION sections)

## E2) Implementation discipline (PR-sized changes)
- Prefer a single focused PR (or commit series) per bug.
- List changed files at the end with 1-2 line rationale each.
- Include a "How to validate" section referencing the checklist items impacted.

## E3) "Do not touch" areas unless necessary
- No UI redesign.
- No renaming/moving files outside the canonical tree.
- No new dependency unless user explicitly accepts.
- No config path guessing (FFmpeg/Potrace/ImageMagick).

---

# F) Practical task recipes (copy/paste prompts)

## F1) Architecture / repo map
"Map the repo: entry points, module responsibilities, data flow, external I/O/tools.
Then list top 5 risks with file pointers."

## F2) Bugfix request (minimal)
"Fix <symptom>. First: identify likely root cause and impacted files. Then propose
a minimal patch plan. Implement only after I confirm."

## F3) UI regression guard
"Before any changes, run the GUI_VALIDATION checklist logically: list what could
regress and what you will re-check after the patch."

## F4) ILDA preview repair (known issue)
"Update core/ilda_preview.py to support Classic format 0 and correct magic
validation. Keep changes minimal. Ensure GUI preview shows frames for both
Classic and Arcade."

## F5) "Cadre parasite" investigation
"Pick 1-3 representative frames. Compare BMP vs SVG on those frames. Confirm
polarity hypothesis. If confirmed, implement controlled inversion before Potrace
(propagate signatures carefully) and validate on those frames."

---

# G) Commands (generic, do not invent tooling)
- Start GUI: `python gui_main.py`
- Import sanity: `python -c "import gui.main_window as m; print('ok')"`
- Follow docs/GUI_VALIDATION.md for the rest.

---

# H) Git hygiene
- Keep commits small and scoped.
- Prefer conventional-ish messages:
  - fix: ...
  - feat: ...
  - refactor: ... (only if explicitly requested and validated)
- Never mix "refactor" and "fix" in the same commit.

---

# I) Additional context (from legacy context_gpt.md)

## I1) Pipeline conventions
- Immutable flow: video -> frames/*.png -> bmp/*.bmp -> svg/*.svg -> <project>.ild.
- Frame naming: frame_0001.png (4-digit, 1-based), same for BMP/SVG.
- Per-project layout: projects/<project>/frames|bmp|svg|preview and <project>.ild.

## I2) External tools
- FFmpeg for frame extraction.
- Potrace for BMP -> SVG.
- ImageMagick may be used for PNG -> BMP (when enabled).
- Paths are configured in core/config.py and must never be guessed.

## I3) Rerun behavior
- Steps must tolerate reruns: either clear target folders or overwrite consistently.
- Avoid mixing outputs from different runs.

## I4) Legacy snapshot files
The `_send_*.py` files in docs/legacy are legacy snapshots and are not used by
the current application runtime. Do not update them unless explicitly asked.
