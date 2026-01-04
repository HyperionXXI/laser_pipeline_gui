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
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        def _compact_row(row: QHBoxLayout) -> None:
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)

        def _compact_control(widget: QWidget, height: int = 24) -> None:
            widget.setFixedHeight(height)

        # Row 1: video
        row_primary = QHBoxLayout()
        row_primary.addWidget(QLabel("Video source:"))
        self.edit_video_path = QLineEdit()
        row_primary.addWidget(self.edit_video_path, 1)
        self.btn_browse_video = QPushButton("Browse...")
        row_primary.addWidget(self.btn_browse_video)
        _compact_row(row_primary)
        _compact_control(self.edit_video_path)
        _compact_control(self.btn_browse_video)
        layout.addLayout(row_primary)

        # Row 2: project/fps/mode + suggestions + actions
        self._suggested_mode_key: str | None = None
        self._suggested_project_name: str | None = None
        row_secondary = QHBoxLayout()
        left_group = QHBoxLayout()
        left_group.addWidget(QLabel("Project name:"))
        self.edit_project = QLineEdit("project_demo")
        left_group.addWidget(self.edit_project)
        left_group.addSpacing(8)
        left_group.addWidget(QLabel("FPS:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(1, 200)
        self.spin_fps.setValue(25)
        left_group.addWidget(self.spin_fps)
        left_group.addSpacing(8)
        left_group.addWidget(QLabel("Max frames (0 = all):"))
        self.spin_max_frames = QSpinBox()
        self.spin_max_frames.setRange(0, 999999)
        self.spin_max_frames.setValue(0)
        left_group.addWidget(self.spin_max_frames)
        left_group.addSpacing(8)
        left_group.addWidget(QLabel("Mode:"))
        self.combo_ilda_mode = QComboBox()
        self.combo_ilda_mode.addItem("Classic (B/W)", "classic")
        self.combo_ilda_mode.addItem("Arcade (experimental)", "arcade")
        self.combo_ilda_mode.setCurrentIndex(0)
        left_group.addWidget(self.combo_ilda_mode)
        _compact_row(left_group)

        right_group = QHBoxLayout()
        right_group.addWidget(QLabel("Suggested mode:"))
        self.label_mode_suggestion = QLabel("-")
        right_group.addWidget(self.label_mode_suggestion)
        right_group.addSpacing(8)
        right_group.addWidget(QLabel("Suggested project:"))
        self.label_project_suggestion = QLabel("-")
        right_group.addWidget(self.label_project_suggestion)
        right_group.addSpacing(8)
        self.btn_apply_mode_suggestion = QPushButton("Apply suggestion")
        self.btn_apply_mode_suggestion.setEnabled(False)
        right_group.addWidget(self.btn_apply_mode_suggestion)
        self.btn_test = QPushButton("Test settings")
        right_group.addWidget(self.btn_test)
        _compact_row(right_group)

        row_secondary.addLayout(left_group)
        row_secondary.addStretch()
        row_secondary.addLayout(right_group)
        _compact_row(row_secondary)
        _compact_control(self.edit_project)
        _compact_control(self.spin_fps)
        _compact_control(self.spin_max_frames)
        _compact_control(self.combo_ilda_mode)
        _compact_control(self.btn_apply_mode_suggestion)
        _compact_control(self.btn_test)
        layout.addLayout(row_secondary)

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
