from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from data.db import DatabaseManager
from data.models import TrackedObject


class DatabaseDialog(QDialog):
    def __init__(self, database: DatabaseManager, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Database Manager")
        self.resize(700, 450)
        self.database = database

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["NORAD ID", "Name", "Category", "TLE History"])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_items)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch(1)
        button_layout.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Manage cached TLE records and object entries."))
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        self.load_items()

    def load_items(self) -> None:
        objects = self.database.get_latest_objects()
        self.table.setRowCount(0)

        for obj in objects:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(obj.norad_id)))
            self.table.setItem(row, 1, QTableWidgetItem(obj.name))
            self.table.setItem(row, 2, QTableWidgetItem(obj.category))
            count = self.database.get_tle_history_count(obj.norad_id)
            self.table.setItem(row, 3, QTableWidgetItem(str(count)))

    def delete_selected(self) -> None:
        selected_ranges = self.table.selectedRanges()
        if not selected_ranges:
            return

        for selected in reversed(selected_ranges):
            for row in range(selected.bottomRow(), selected.topRow() - 1, -1):
                item = self.table.item(row, 0)
                if item is None:
                    continue
                norad_id = int(item.text())
                self.database.delete_tle_history(norad_id)
                self.database.delete_object(norad_id)
                self.table.removeRow(row)

        self.load_items()
        # inform main window log if available
        try:
            parent = self.parent()
            if parent is not None and hasattr(parent, "log_dialog"):
                parent.log_dialog.append("Deleted selected DB entries")
        except Exception:
            pass
