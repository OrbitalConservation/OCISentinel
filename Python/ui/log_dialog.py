from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout


class LogDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Action Log")
        self.resize(600, 400)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)

        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.text_edit)
        layout.addLayout(button_layout)

    def append(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.text_edit.append(f"[{timestamp}] {message}")

    def clear(self) -> None:
        self.text_edit.clear()
