from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from config import DB_FILE, SettingsManager
from data.db import DatabaseManager
from data.fetcher import CelesTrakFetcher
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    settings_manager = SettingsManager()
    settings = settings_manager.load()

    database_manager = DatabaseManager(DB_FILE)
    fetcher = CelesTrakFetcher(settings.verify_ssl)

    window = MainWindow(settings_manager, database_manager, fetcher)
    window.show()

    result = app.exec()
    database_manager.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
