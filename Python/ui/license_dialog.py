from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QTextEdit


class LicenseDialog(QDialog):
    def __init__(self, license_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Licence")
        self.setModal(True)
        self.resize(620, 520)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        header = QLabel("Licence Agreement")
        header.setAlignment(Qt.AlignCenter)
        header.setObjectName("licenseHeader")
        main_layout.addWidget(header)

        body = QTextEdit()
        body.setReadOnly(True)
        try:
            body.setPlainText(license_path.read_text(encoding="utf-8"))
        except Exception as exc:
            body.setPlainText(f"Unable to load licence text: {exc}")
        main_layout.addWidget(body)

        close_button = QPushButton("Close")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

        ###
        
        # self.setStyleSheet(
        #     "#licenseHeader { font-size: 20px; font-weight: bold; margin-bottom: 8px; }"
        #     "QTextEdit { background: #111827; color: #f3f4f6; border: 1px solid #4b5563; padding: 12px; }"
        #     "QDialog { background: #0f172a; color: #f3f4f6; }"
        #     "QPushButton { min-height: 36px; padding: 8px 16px; }"
        # )
        
