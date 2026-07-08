from __future__ import annotations

from config import APP_NAME, APP_VERSION
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QTextEdit, QPushButton, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class AboutDialog(QDialog):
    def __init__(self, parent=None, theme: str = "light") -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setModal(True)
        self.resize(560, 420)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(14)

        header = QLabel(f"{APP_NAME} (v{APP_VERSION})")
        header.setAlignment(Qt.AlignCenter)
        header.setObjectName("aboutHeader")
        main_layout.addWidget(header)

        summary = QLabel(
            "A lightweight orbital awareness and tracking tool for public use. "
            "Fetches live CelesTrak TLE feeds, caches data locally, and visualises "
            "satellite/debris positions on an interactive wireframe Earth projection."
        )
        summary.setWordWrap(True)
        summary.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(summary)

        details_widget = QWidget()
        details_layout = QHBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(12)

        left_info = QTextEdit()
        left_info.setReadOnly(True)
        left_info.setPlainText(
            "Features:\n"
            "• Live CelesTrak subgroup fetching with offline cache support\n"
            "• Selectable fetch groups and plot filters for debris / active objects\n"
            "• Skyfield-based propagation with ground-track and orbit path visuals\n"
            "• Local SQLite storage for objects, TLE history, and plot caching\n"
            "• Background fetch worker with progress feedback and cancellation\n"
            "• Support for SSL verification toggle and offline mode\n"
            "\n"
            "Usage Notes:\n"
            "• Use 'Plot Positions' to refresh the current visual state.\n"
            "• Select an object in the left panel to show its latest trajectory and history.\n"
            "• Use settings to choose which groups are fetched versus plotted.\n"
        )
        details_layout.addWidget(left_info)

        right_info = QTextEdit()
        right_info.setReadOnly(True)
        right_info.setPlainText(
            "About This Build:\n"
            f"Application: {APP_NAME}\n"
            f"Version: {APP_VERSION}\n"
            "Source: Public orbital tracking data from CelesTrak\n"
            "Visualization: 2D wireframe globe with projected orbit/ground-track paths\n"
            "Limitations: Not a certified decision support system; use for situational awareness only.\n"
            "\n"
            "Contact:\n"
            "Oakshift Software\nor\nOrbital Conservation Institute\n\n"
            "Email:\norbitalconservation@gmail.com\nor\noakshiftsoftware@gmail.com\n\n"
            "Website:\nhttps://orbitalconservation.github.io\nor\nhttps://oakshift.co.uk"
        )
        details_layout.addWidget(right_info)

        main_layout.addWidget(details_widget)

        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(close_btn)
        main_layout.addLayout(button_layout)

        self.setStyleSheet(self._dialog_stylesheet(theme))

    def _dialog_stylesheet(self, theme: str) -> str:
        if theme == "dark":
            return (
                "#aboutHeader { font-size: 18px; font-weight: bold; margin-bottom: 12px; }"
                "QLabel { font-size: 14px; color: #e8eef4; }"
                "QTextEdit { background: #1d283b; color: #e8eef4; border: 1px solid #5a6f92; padding: 10px; }"
                "QDialog { background: #121b2d; color: #e8eef4; }"
                "QPushButton { min-height: 32px; padding: 6px 12px; background: #1f2937; color: #e8eef4; border: 1px solid #475569; }"
                "QPushButton:hover { background: #334155; }"
            )
        return (
            "#aboutHeader { font-size: 18px; font-weight: bold; margin-bottom: 12px; }"
            "QLabel { font-size: 14px; color: #0f172a; }"
            "QTextEdit { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; padding: 10px; }"
            "QDialog { background: #f8fafc; color: #0f172a; }"
            "QPushButton { min-height: 32px; padding: 6px 12px; background: #e2e8f0; color: #0f172a; border: 1px solid #94a3b8; }"
            "QPushButton:hover { background: #cbd5e1; }"
        )
