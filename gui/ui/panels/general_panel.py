from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class GeneralPanel(QGroupBox):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("General settings", parent)
        self.setObjectName("sectionGroup")

        layout = QVBoxLayout(self)

        # Video row
        row_video = QHBoxLayout()
        row_video.addWidget(QLabel("Video source:"))
        self.edit_video_path = QLineEdit()
        row_video.addWidget(self.edit_video_path)
        self.btn_browse_video = QPushButton("Browse...")
        row_video.addWidget(self.btn_browse_video)
        layout.addLayout(row_video)

        # Project row
        row_project = QHBoxLayout()
        row_project.addWidget(QLabel("Project name:"))
        self.edit_project = QLineEdit("project_demo")
        row_project.addWidget(self.edit_project)
        layout.addLayout(row_project)

        # FPS row
        row_fps = QHBoxLayout()
        row_fps.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        row_fps.addWidget(self.spin_fps)
        layout.addLayout(row_fps)

        # Max frames row (global)
        row_max = QHBoxLayout()
        row_max.addWidget(QLabel("Max frames (0 = all):"))
        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(0, 999999)
        self.spin_max_frames.setValue(0)
        row_max.addWidget(self.spin_max_frames)
        layout.addLayout(row_max)

        # Test button
        self.btn_test = QPushButton("Test settings")
        layout.addWidget(self.btn_test)
