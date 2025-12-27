from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
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

        # Mode row
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Mode:"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classic (B/W)", "classic")
        self.combo_ilda_mode.addItem("Arcade (experimental)", "arcade")
        self.combo_ilda_mode.setCurrentIndex(0)
        row_mode.addWidget(self.combo_ilda_mode)
        layout.addLayout(row_mode)

        # Mode suggestion row
        self._suggested_mode_key: str | None = None
        self._suggested_project_name: str | None = None
        row_suggest = QHBoxLayout()
        row_suggest.addWidget(QLabel("Suggested mode:"))
        self.label_mode_suggestion = QLabel("—")
        row_suggest.addWidget(self.label_mode_suggestion, 1)
        self.btn_apply_mode_suggestion = QPushButton("Apply suggestion")
        self.btn_apply_mode_suggestion.setEnabled(False)
        row_suggest.addWidget(self.btn_apply_mode_suggestion)
        layout.addLayout(row_suggest)

        row_project_suggest = QHBoxLayout()
        row_project_suggest.addWidget(QLabel("Suggested project:"))
        self.label_project_suggestion = QLabel("—")
        row_project_suggest.addWidget(self.label_project_suggestion, 1)
        layout.addLayout(row_project_suggest)

        # Test button
        self.btn_test = QPushButton("Test settings")
        layout.addWidget(self.btn_test)

    def set_mode_suggestion(self, mode_key: str, reason: str = "") -> None:
        self._suggested_mode_key = mode_key
        label = self._mode_label_for_key(mode_key)
        if reason:
            label = f"{label} ({reason})"
        self.label_mode_suggestion.setText(label)
        self.btn_apply_mode_suggestion.setEnabled(True)

    def clear_mode_suggestion(self) -> None:
        self._suggested_mode_key = None
        self.label_mode_suggestion.setText("—")
        self.btn_apply_mode_suggestion.setEnabled(False)

    def get_suggested_mode_key(self) -> str | None:
        return self._suggested_mode_key

    def apply_suggested_mode(self) -> None:
        if self._suggested_mode_key:
            idx = self.combo_ilda_mode.findData(self._suggested_mode_key)
            if idx >= 0:
                self.combo_ilda_mode.setCurrentIndex(idx)
        if self._suggested_project_name:
            self.edit_project.setText(self._suggested_project_name)

    def set_project_suggestion(self, project_name: str) -> None:
        self._suggested_project_name = project_name
        self.label_project_suggestion.setText(project_name)
        self.btn_apply_mode_suggestion.setEnabled(True)

    def clear_project_suggestion(self) -> None:
        self._suggested_project_name = None
        self.label_project_suggestion.setText("—")

    def get_suggested_project_name(self) -> str | None:
        return self._suggested_project_name

    @staticmethod
    def _mode_label_for_key(mode_key: str) -> str:
        key = (mode_key or "").strip().lower()
        if key == "arcade":
            return "Arcade (experimental)"
        return "Classic (B/W)"
