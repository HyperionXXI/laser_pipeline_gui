from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMainWindow


@dataclass(frozen=True)
class MenuCallbacks:
    """Callbacks provided by the main window.

We keep this simple: the MainWindow already exposes methods,
and we inject them here to avoid importing MainWindow (circular dependencies).
"""

    on_new_project: Callable[[], None]
    on_open_project: Callable[[], None]
    on_open_video: Callable[[], None]
    on_clear_outputs: Callable[[], None]
    on_reveal_project: Callable[[], None]
    on_refresh_previews: Callable[[], None]
    on_toggle_fullscreen: Callable[[], None]
    on_about: Callable[[], None]
    on_exit: Callable[[], None]


def build_menu(win: QMainWindow, cb: MenuCallbacks) -> None:
    """Build the menu bar.

    NOTE: for compatibility, we also expose setup_menus() and build_menus()
    which call this function.
    """
    menu = win.menuBar()

    file_menu = menu.addMenu("File")

    act_new = QAction("New Project...", win)
    act_new.setShortcut(QKeySequence("Ctrl+N"))
    act_new.triggered.connect(cb.on_new_project)
    file_menu.addAction(act_new)

    act_open_proj = QAction("Open Project...", win)
    act_open_proj.setShortcut(QKeySequence("Ctrl+Shift+O"))
    act_open_proj.triggered.connect(cb.on_open_project)
    file_menu.addAction(act_open_proj)

    act_open_vid = QAction("Open Video...", win)
    act_open_vid.setShortcut(QKeySequence("Ctrl+O"))
    act_open_vid.triggered.connect(cb.on_open_video)
    file_menu.addAction(act_open_vid)

    file_menu.addSeparator()

    act_exit = QAction("Exit", win)
    act_exit.setShortcut(QKeySequence("Ctrl+Q"))
    act_exit.triggered.connect(cb.on_exit)
    file_menu.addAction(act_exit)

    proj_menu = menu.addMenu("Project")

    act_clear = QAction("Clear generated outputs...", win)
    act_clear.triggered.connect(cb.on_clear_outputs)
    proj_menu.addAction(act_clear)

    act_reveal = QAction("Reveal project in Explorer", win)
    act_reveal.triggered.connect(cb.on_reveal_project)
    proj_menu.addAction(act_reveal)

    act_refresh = QAction("Refresh previews", win)
    act_refresh.setShortcut(QKeySequence("F5"))
    act_refresh.triggered.connect(cb.on_refresh_previews)
    proj_menu.addAction(act_refresh)

    view_menu = menu.addMenu("View")
    act_fullscreen = QAction("Toggle Fullscreen", win)
    act_fullscreen.setShortcut(QKeySequence("F11"))
    act_fullscreen.triggered.connect(cb.on_toggle_fullscreen)
    view_menu.addAction(act_fullscreen)

    help_menu = menu.addMenu("Help")
    act_about = QAction("About", win)
    act_about.setShortcut(QKeySequence("F1"))
    act_about.triggered.connect(cb.on_about)
    help_menu.addAction(act_about)


# Compatibility: names used in earlier refactor attempts.
def setup_menus(win: QMainWindow, cb: MenuCallbacks) -> None:
    build_menu(win, cb)


def build_menus(win: QMainWindow, cb: MenuCallbacks) -> None:
    build_menu(win, cb)
