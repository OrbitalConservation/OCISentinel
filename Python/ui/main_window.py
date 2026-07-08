from __future__ import annotations

from functools import partial
from typing import cast
import math
from datetime import timedelta

import requests
from PySide6.QtCore import QThread, Qt, QTimer
import shiboken6
from PySide6.QtGui import QAction
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QProgressDialog,
    QSplitter,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QMenu,
)

from config import AppSettings, APP_ICON_PATH, APP_NAME, APP_VERSION, SettingsManager, CELESTRAK_DATA_GROUPS
from data.db import DatabaseManager
from data.fetcher import CelesTrakFetcher
from pathlib import Path
from data.models import TrackedObject
from skyfield.api import EarthSatellite, load
from ui.database_dialog import DatabaseDialog
from ui.fetch_worker import FetchWorker
from ui.log_dialog import LogDialog
from ui.settings_dialog import SettingsDialog
from ui.visualization_widget import VisualizationWidget
from ui.about_dialog import AboutDialog
from ui.license_dialog import LicenseDialog


class MainWindow(QMainWindow):
    def __init__(self, settings_manager: SettingsManager, database: DatabaseManager, fetcher: CelesTrakFetcher) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings_manager.settings
        self.database = database
        self.fetcher = fetcher
        self.fetch_thread: QThread | None = None
        self.fetch_worker: FetchWorker | None = None
        self.loading_dialog: QProgressDialog | None = None
        self.plot_loading_dialog: QProgressDialog | None = None
        self.log_dialog = LogDialog(self)
        self.setWindowTitle(f"{APP_NAME} (v{APP_VERSION})")
        self.resize(1100, 720)
        icon = QIcon(QPixmap(str(APP_ICON_PATH)))
        if not icon.isNull():
            self.setWindowIcon(icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by NORAD ID")
        self.search_input.textChanged.connect(self.refresh_object_list)

        self.category_label = QLabel(f"Category: {self.settings.default_category}")

        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.open_settings)

        self.refresh_button = QPushButton("Refresh Data")
        self.refresh_button.clicked.connect(self.refresh_data)
        self.refresh_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.plot_button = QPushButton("Plot Positions")
        self.plot_button.clicked.connect(self.plot_positions)
        self.plot_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.object_list = QTreeWidget()
        self.object_list.setHeaderLabels(["Objects"]) 
        self.object_list.setRootIsDecorated(True)
        self.object_list.itemSelectionChanged.connect(lambda: self.display_object_details(self.object_list.currentItem(), None))

        self.detail_label = QLabel("Select an object to show details and prediction data.")
        self.detail_label.setWordWrap(True)
        self.detail_label.setAlignment(Qt.AlignTop)

        self.visualization = VisualizationWidget()
        self.visualization.show_debug_overlay = self.settings.show_debug_overlay
        self.visualization.plot_progress.connect(self._on_plot_progress)
        self.visualization.plot_complete.connect(self._on_plot_complete)
        # apply rendering preferences from settings
        try:
            self.visualization.render_all_positions = bool(self.settings.render_all_positions)
        except Exception:
            self.visualization.render_all_positions = False
        self.visualization.max_render_points = 5000
        self.current_positions: list[dict] = []

        self.apply_theme(self.settings.theme)

        self.collision_summary = QLabel("Nearby objects and predicted close approaches")
        self.collision_summary.setWordWrap(True)
        self.collision_table = QTableWidget(0, 4)
        self.collision_table.setHorizontalHeaderLabels(["Object A", "Object B", "Distance (km)", "Risk"])
        self.collision_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.collision_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.collision_table.setSelectionBehavior(QTableWidget.SelectRows)

        self.prediction_progress = QProgressBar()
        self.prediction_progress.setRange(0, 10)
        self.prediction_progress.setTextVisible(True)
        self.prediction_progress.setValue(0)

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.search_input)
        left_layout.addWidget(self.category_label)

        button_row = QHBoxLayout()
        button_row.addWidget(self.refresh_button, 2)
        button_row.addWidget(self.plot_button, 2)
        self.show_all_button = QPushButton("Show All")
        self.show_all_button.clicked.connect(self._show_all_positions)
        button_row.addWidget(self.settings_button, 1)
        button_row.addWidget(self.show_all_button, 1)
        left_layout.addLayout(button_row)

        left_layout.addWidget(self.object_list)

        right_layout = QVBoxLayout()
        self.tab_widget = QTabWidget()

        orbit_tab = QWidget()
        orbit_layout = QVBoxLayout()
        orbit_layout.addWidget(QLabel("Object Details"))
        orbit_layout.addWidget(self.detail_label)
        orbit_layout.addWidget(self.prediction_progress)
        orbit_layout.addWidget(self.visualization)
        orbit_tab.setLayout(orbit_layout)

        collision_tab = QWidget()
        collision_layout = QVBoxLayout()
        collision_layout.addWidget(self.collision_summary)
        collision_layout.addWidget(self.collision_table)
        collision_tab.setLayout(collision_layout)

        self.tab_widget.addTab(orbit_tab, "Orbit View")
        self.tab_widget.addTab(collision_tab, "Collision Risk")

        right_layout.addWidget(self.tab_widget)

        left_widget = QWidget()
        left_widget.setLayout(left_layout)
        right_widget = QWidget()
        right_widget.setLayout(right_layout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        central_widget = QWidget()
        layout = QHBoxLayout(central_widget)
        layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        self.statusBar().showMessage("Ready")
        self._create_menu()
        self.refresh_object_list()
        self._start_auto_refresh()
        # startup behavior: refresh if enabled, otherwise plot stored cached data if available
        try:
            if not self.settings.offline_mode and getattr(self.settings, "refresh_on_startup", True):
                QTimer.singleShot(200, self.refresh_data)
            else:
                stored_objects = self.database.get_objects(category=self.settings.default_category)
                if stored_objects:
                    QTimer.singleShot(200, lambda: self.load_cached_positions(stored_objects))
        except Exception:
            pass

    def _create_menu(self) -> None:
        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_data)
        file_menu.addAction(refresh_action)

        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        help_menu = menu.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.open_about)
        help_menu.addAction(about_action)

        license_action = QAction("Licence", self)
        license_action.triggered.connect(self.open_licence)
        help_menu.addAction(license_action)

        log_action = QAction("Log", self)
        log_action.triggered.connect(self.open_log)
        help_menu.addAction(log_action)

        db_action = QAction("Database", self)
        db_action.triggered.connect(self.open_database_manager)
        help_menu.addAction(db_action)

    def _start_auto_refresh(self) -> None:
        if self.settings.auto_refresh:
            timer = QTimer(self)
            timer.timeout.connect(self.refresh_data)
            timer.start(self.settings.update_frequency_minutes * 60 * 1000)
            self.auto_refresh_timer = timer

    def apply_theme(self, theme: str) -> None:
        if theme == "dark":
            stylesheet = self._dark_theme_stylesheet()
        else:
            stylesheet = self._light_theme_stylesheet()

        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)

    def _dark_theme_stylesheet(self) -> str:
        return """
QWidget { background: #0f172a; color: #e2e8f0; }
QLineEdit, QTextEdit, QComboBox, QScrollArea, QSpinBox, QDoubleSpinBox, QTabWidget, QTableWidget, QTreeWidget { background: #14223e; color: #e2e8f0; border: 1px solid #334155; }
QHeaderView::section { background: #1f2a44; color: #e2e8f0; border: 1px solid #334155; }
QPushButton { background: #1f2937; color: #f8fafc; border: 1px solid #475569; padding: 6px 10px; }
QPushButton:hover { background: #334155; }
QLabel { color: #e2e8f0; }
QTabBar::tab { background: #1f2937; color: #e2e8f0; padding: 8px; }
QTabBar::tab:selected { background: #0f172a; border-bottom: 2px solid #60a5fa; }
QStatusBar { background: #111827; color: #cbd5e1; }
QProgressBar { background: #1f2937; color: #e2e8f0; border: 1px solid #334155; padding: 2px; text-align: center; }
QProgressBar::chunk { background: #60a5fa; }
QTreeView, QTableView { alternate-background-color: #0f172a; selection-background-color: #2563eb; selection-color: #ffffff; }
"""

    def _light_theme_stylesheet(self) -> str:
        return """
QWidget { background: #f8fafc; color: #0f172a; }
QLineEdit, QTextEdit, QComboBox, QScrollArea, QSpinBox, QDoubleSpinBox, QTabWidget, QTableWidget, QTreeWidget { background: #ffffff; color: #0f172a; border: 1px solid #cbd5e1; }
QHeaderView::section { background: #e2e7ef; color: #0f172a; border: 1px solid #cbd5e1; }
QPushButton { background: #e2e8f0; color: #0f172a; border: 1px solid #94a3b8; padding: 6px 10px; }
QPushButton:hover { background: #cbd5e1; }
QLabel { color: #0f172a; }
QTabBar::tab { background: #e2e8f0; color: #0f172a; padding: 8px; }
QTabBar::tab:selected { background: #f8fafc; border-bottom: 2px solid #2563eb; }
QStatusBar { background: #e2e8f0; color: #0f172a; }
QProgressBar { background: #e2e8f0; color: #0f172a; border: 1px solid #cbd5e1; padding: 2px; text-align: center; }
QProgressBar::chunk { background: #2563eb; }
QTreeView, QTableView { alternate-background-color: #f8fafc; selection-background-color: #2563eb; selection-color: #ffffff; }
"""

    def refresh_data(self) -> None:
        if self.settings.offline_mode:
            self.statusBar().showMessage("Offline mode: using cached data")
            stored_objects = self.database.get_objects(category=self.settings.default_category)
            if stored_objects:
                self.load_cached_positions(stored_objects)
            return

        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage("Refreshing data...")
        self.fetcher.verify_ssl = self.settings.verify_ssl

        enabled_subgroups = self.settings.enabled_data_subgroups
        self.fetch_worker = FetchWorker(self.fetcher, self.settings.default_category, enabled_subgroups=enabled_subgroups)
        self.fetch_thread = QThread(self)
        self.fetch_worker.moveToThread(self.fetch_thread)
        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self.on_fetch_finished)
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.error.connect(self.on_fetch_error)
        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.error.connect(self.fetch_thread.quit)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_worker.error.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
        self.fetch_thread.finished.connect(self._on_fetch_thread_finished)

        self.loading_dialog = QProgressDialog("Loading orbital data...", "Cancel", 0, 0, self)
        self.loading_dialog.setWindowTitle("Loading")
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setCancelButtonText("Cancel")
        self.loading_dialog.canceled.connect(self._cancel_fetch)
        self.loading_dialog.show()

        self.fetch_thread.start()

    def load_cached_positions(self, objects: list[TrackedObject]) -> None:
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage("Loading cached positions...")
        enabled_subgroups = self.settings.enabled_data_subgroups
        self.fetch_worker = FetchWorker(
            self.fetcher,
            self.settings.default_category,
            cached_objects=objects,
            enabled_subgroups=enabled_subgroups,
        )

        self.fetch_thread = QThread(self)
        self.fetch_worker.moveToThread(self.fetch_thread)
        self.fetch_thread.started.connect(self.fetch_worker.run)
        self.fetch_worker.finished.connect(self.on_fetch_finished)
        self.fetch_worker.progress.connect(self._on_fetch_progress)
        self.fetch_worker.error.connect(self.on_fetch_error)
        self.fetch_worker.finished.connect(self.fetch_thread.quit)
        self.fetch_worker.error.connect(self.fetch_thread.quit)
        self.fetch_worker.finished.connect(self.fetch_worker.deleteLater)
        self.fetch_worker.error.connect(self.fetch_worker.deleteLater)
        self.fetch_thread.finished.connect(self.fetch_thread.deleteLater)
        self.fetch_thread.finished.connect(self._on_fetch_thread_finished)

        self.loading_dialog = QProgressDialog("Loading cached positions...", "Cancel", 0, 0, self)
        self.loading_dialog.setWindowTitle("Loading")
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setCancelButtonText("Cancel")
        self.loading_dialog.canceled.connect(self._cancel_fetch)
        self.loading_dialog.show()

        self.fetch_thread.start()

    def on_fetch_finished(self, payload: object) -> None:
        # payload is expected to be a dict with 'objects' and 'positions'
        if self.loading_dialog is not None:
            self.loading_dialog.hide()
            self.loading_dialog = None

        data = payload or {}
        objects = data.get("objects", []) if isinstance(data, dict) else []
        positions = data.get("positions", []) if isinstance(data, dict) else []
        self.log_dialog.append(f"Fetch completed: {len(objects)} objects, {len(positions)} positions")

        self.current_positions = positions
        self._apply_plot_filters(positions)

        # perform bulk upsert to avoid UI-blocking per-row commits
        try:
            if objects:
                self.database.upsert_objects(objects)
                cache_load = getattr(self.fetch_worker, "cached_objects", None) is not None
                if self.settings.store_tle_history and not cache_load:
                    self.database.insert_tle_history_bulk(objects)
        except Exception:
            # fall back to per-object upsert on error
            cache_load = getattr(self.fetch_worker, "cached_objects", None) is not None
            for obj in objects:
                try:
                    self.database.upsert_object(obj)
                    if self.settings.store_tle_history and not cache_load:
                        self.database.insert_tle_history(obj)
                except Exception:
                    continue

        self.refresh_object_list()
        # update visualization stats, positions, and collision risk
        try:
            self.visualization.set_stats(len(objects), len(positions))
            self.visualization.plot_positions(positions)
            self._update_collision_summary(positions)
            # if nothing was produced, dump a small debug summary to disk for inspection
        except Exception:
            pass
        self.current_positions = positions
        self._update_collision_summary(positions)
        self.refresh_button.setEnabled(True)
        self.statusBar().showMessage("Data refreshed successfully")

    def plot_positions(self) -> None:
        positions = self.current_positions or []
        if not positions:
            self.visualization.repaint()
            self.statusBar().showMessage("No position data available to plot")
            return

        selected_norad = self.visualization.selected_norad
        if selected_norad is not None:
            filtered = [p for p in positions if int(p.get("norad_id", -1)) == int(selected_norad)]
            if not filtered:
                filtered = []
        else:
            try:
                filtered = [p for p in positions if (p.get("category") in (getattr(self.settings, "enabled_plot_subgroups", []) or []))]
                if not getattr(self.settings, "enabled_plot_subgroups", []):
                    filtered = positions
            except Exception:
                filtered = positions

        self._apply_plot_filters(filtered)
        self.statusBar().showMessage(f"Wireframe plot refreshed ({len(filtered)} points)")

    def _update_collision_summary(self, positions: list[dict]) -> None:
        self.collision_table.setRowCount(0)
        pairs = self._find_close_pairs(positions)
        if not pairs:
            self.collision_summary.setText("No nearby objects or predicted close approaches detected.")
            return

        self.collision_summary.setText("Tracked items within 50 km of each other or showing elevated risk.")
        for a, b, distance_km, risk in pairs:
            row = self.collision_table.rowCount()
            self.collision_table.insertRow(row)
            self.collision_table.setItem(row, 0, QTableWidgetItem(f"{a['norad_id']} — {a['name']}"))
            self.collision_table.setItem(row, 1, QTableWidgetItem(f"{b['norad_id']} — {b['name']}"))
            self.collision_table.setItem(row, 2, QTableWidgetItem(f"{distance_km:.1f}"))
            self.collision_table.setItem(row, 3, QTableWidgetItem(risk))

    def _find_close_pairs(self, positions: list[dict]) -> list[tuple[dict, dict, float, str]]:
        results: list[tuple[dict, dict, float, str]] = []
        if len(positions) < 2:
            return results

        def _angular_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))
            return 6371.0 * c

        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                a = positions[i]
                b = positions[j]
                try:
                    dist = _angular_distance(
                        float(a.get("lat", 0.0)),
                        float(a.get("lon", 0.0)),
                        float(b.get("lat", 0.0)),
                        float(b.get("lon", 0.0)),
                    )
                    risk = "Low"
                    if dist < 10:
                        risk = "High"
                    elif dist < 30:
                        risk = "Medium"
                    if dist <= 50:
                        results.append((a, b, dist, risk))
                except Exception:
                    continue
        results.sort(key=lambda item: item[2])
        return results

    def on_fetch_error(self, message: str, exc: object) -> None:
        if self.loading_dialog is not None:
            self.loading_dialog.hide()
            self.loading_dialog = None

        self.log_dialog.append(f"Fetch error: {message}")
        self.refresh_button.setEnabled(True)
        self.statusBar().showMessage("Failed to refresh data")
        if isinstance(exc, requests.exceptions.SSLError) and self.settings.verify_ssl:
            choice = QMessageBox.question(
                self,
                "SSL Verification Failed",
                "Certificate verification failed while downloading TLE data. "
                "Would you like to retry with SSL verification disabled?\n\n"
                "If you choose Yes, the app will download data without verifying the certificate.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if choice == QMessageBox.Yes:
                self.settings.verify_ssl = False
                self.settings_manager.save(self.settings)
                self.fetcher.verify_ssl = False
                self.refresh_data()
                return

        QMessageBox.warning(self, "Refresh Error", f"{message}")

    def _cancel_fetch(self) -> None:
        """User canceled the loading dialog; request worker stop and try to clean up thread."""
        try:
            self.log_dialog.append("Fetch canceled by user")
            if self.fetch_worker is not None:
                try:
                    self.fetch_worker.stop()
                except Exception:
                    pass
            # avoid calling into a deleted C++ object by checking validity first
            try:
                if getattr(self, "fetch_thread", None) is not None and shiboken6.isValid(self.fetch_thread):
                    if self.fetch_thread.isRunning():
                        self.fetch_thread.quit()
                        self.fetch_thread.wait(2000)
            except Exception:
                # best-effort cleanup; ignore errors from deleted Qt wrappers
                pass
            finally:
                self.fetch_thread = None
        finally:
            if self.loading_dialog is not None:
                self.loading_dialog.hide()
                self.loading_dialog = None

    def closeEvent(self, event) -> None:
        """Ensure any running fetch thread is stopped before closing the window."""
        try:
            if self.fetch_worker is not None:
                try:
                    self.fetch_worker.stop()
                except Exception:
                    pass
            if getattr(self, "fetch_thread", None) is not None:
                try:
                    if shiboken6.isValid(self.fetch_thread) and self.fetch_thread.isRunning():
                        self.fetch_thread.quit()
                        self.fetch_thread.wait(3000)
                except Exception:
                    pass
                finally:
                    self.fetch_thread = None
                    self.fetch_worker = None
        except Exception:
            pass
        super().closeEvent(event)

    def _on_fetch_thread_finished(self) -> None:
        self.fetch_thread = None
        self.fetch_worker = None

    def refresh_object_list(self) -> None:
        """Populate the left-side tree with categories/subgroups and objects.

        Shows counts of cached TLE history next to each object.
        """
        search_text = self.search_input.text().strip()
        category = self.settings.default_category
        norad_id: int | None = None

        if search_text:
            if search_text.isdigit():
                norad_id = int(search_text)
            else:
                # perform a name substring search (case-insensitive)
                objs = self.database.get_objects(name=search_text)
                self.object_list.clear()
                if not objs:
                    return
                top = QTreeWidgetItem(self.object_list, ["Search Results"])
                top.setFirstColumnSpanned(True)
                for obj in objs:
                    child = QTreeWidgetItem(top, [f"{obj.norad_id} — {obj.name}"])
                    child.setData(0, Qt.UserRole, obj)
                top.setExpanded(True)
                return

        self.object_list.clear()

        # Helper to add object child under a parent tree item
        def _add_obj_child(parent_item: QTreeWidgetItem, obj: TrackedObject) -> None:
            count = self.database.get_tle_history_count(obj.norad_id)
            label = f"{obj.norad_id} — {obj.name} [{count}]"
            child = QTreeWidgetItem(parent_item, [label])
            child.setData(0, Qt.UserRole, obj)

        # If a numeric search is provided, show only that object (if present)
        if norad_id is not None:
            obj = self.database.get_object(norad_id)
            if obj is None:
                return
            top = QTreeWidgetItem(self.object_list, [f"{obj.category}"])
            top.setFirstColumnSpanned(True)
            _add_obj_child(top, obj)
            top.setExpanded(True)
            return

        # Build tree based on CELESTRAK_DATA_GROUPS: top-level groups and subgroups
        for top_group, submap in CELESTRAK_DATA_GROUPS.items():
            # If user selected a specific top-level category, skip other tops
            if category != "all" and category != top_group:
                continue
            top_item = QTreeWidgetItem(self.object_list, [top_group.capitalize()])
            top_item.setFirstColumnSpanned(True)
            for subgroup_key in submap:
                # If default category filters subgroups directly, apply that
                if category != "all" and category != top_group and category != subgroup_key:
                    continue
                sub_item = QTreeWidgetItem(top_item, [subgroup_key])
                sub_item.setFirstColumnSpanned(True)
                # fetch objects for this subgroup (category=subgroup_key)
                objs = self.database.get_objects(category=subgroup_key)
                for obj in objs:
                    _add_obj_child(sub_item, obj)
                if sub_item.childCount() == 0:
                    # remove empty subgroup
                    top_item.removeChild(sub_item)
            if top_item.childCount() == 0:
                # if no subgroups had children, remove top
                idx = self.object_list.indexOfTopLevelItem(top_item)
                if idx != -1:
                    self.object_list.takeTopLevelItem(idx)

    def display_object_details(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        if current is None:
            self.detail_label.setText("Select an object to show details and prediction data.")
            self.visualization.set_selected_norad(None)
            self.visualization.set_selected_history_orbits([])
            self.visualization.set_selected_last_position(None)
            self._apply_plot_filters(self.current_positions or [])
            return

        obj = cast(TrackedObject, current.data(0, Qt.UserRole))
        description = (
            f"Name: {obj.name}\n"
            f"NORAD ID: {obj.norad_id}\n"
            f"Category: {obj.category}\n"
            f"Epoch: {obj.epoch}\n\n"
            f"TLE Line1: {obj.line1}\n"
            f"TLE Line2: {obj.line2}\n\n"
            "Predicting next 2 hours..."
        )
        self.detail_label.setText(description)
        history_progress = self.database.get_tle_history_count(obj.norad_id)
        self._update_prediction_progress(history_progress)

        # load stored TLE history for this object and render its orbit history
        history_records = self.database.get_tle_history(obj.norad_id)
        history_orbits: list[list[tuple[float, float, float]]] = []
        last_position: dict | None = None

        if history_records:
            ts = load.timescale()
            now = ts.now()
            for record in history_records[:3]:
                try:
                    sat = EarthSatellite(record.line1, record.line2, f"{obj.name}-{record.fetch_time}", ts)
                    times = [now + timedelta(seconds=i * 60) for i in range(0, 30)]
                    orbit_path: list[tuple[float, float, float]] = []
                    for t in times:
                        point = sat.at(t).subpoint()
                        orbit_path.append((
                            float(point.latitude.degrees),
                            float(point.longitude.degrees),
                            float(point.elevation.km if hasattr(point, 'elevation') else 0.0)
                        ))
                    history_orbits.append(orbit_path)
                except Exception:
                    continue
            if history_orbits and history_orbits[0]:
                last_position = {
                    "lat": history_orbits[0][-1][0],
                    "lon": history_orbits[0][-1][1],
                    "alt_km": history_orbits[0][-1][2],
                }

        self.visualization.set_selected_norad(obj.norad_id)
        self.visualization.set_selected_history_orbits(history_orbits)
        self.visualization.set_selected_last_position(last_position)
        self.plot_positions()

        try:
            latitudes, longitudes = obj.propagate_positions(minutes=120, steps=24)
            position_summary = (
                f"Latest latitude: {latitudes[-1]:.3f}°\n"
                f"Latest longitude: {longitudes[-1]:.3f}°\n"
                f"Path points: {len(latitudes)}"
            )
            self.detail_label.setText(description + "\n" + position_summary)
        except Exception:
            if history_progress >= 10:
                self.detail_label.setText(description + "\nPrediction unavailable due to orbit propagation failure.")
            else:
                self.detail_label.setText(
                    description +
                    f"\nPrediction unavailable: stored history {history_progress}/10. "
                    "Collect more TLE updates to enable trajectory projection."
                )

        # focus visualization on the selected object's NORAD
        try:
            self.visualization.set_selected_norad(obj.norad_id)
        except Exception:
            pass

    def _update_prediction_progress(self, history_count: int) -> None:
        _required_history = 10
        self.prediction_progress.setValue(min(history_count, _required_history))
        if history_count >= _required_history:
            self.prediction_progress.setFormat("Prediction readiness: sufficient history")
        else:
            self.prediction_progress.setFormat(
                f"Prediction readiness: {history_count}/{_required_history} TLE records stored"
            )

    def _on_fetch_progress(self, phase: str | int, current: int, total: int) -> None:
        try:
            if self.loading_dialog is None:
                return
            if total and total > 0:
                self.loading_dialog.setRange(0, total)
                self.loading_dialog.setValue(current)
                phase_label = str(phase).capitalize() if isinstance(phase, str) else "Loading"
                self.loading_dialog.setLabelText(f"{phase_label} orbital data... ({current}/{total})")
            else:
                self.loading_dialog.setRange(0, 0)
        except Exception:
            pass

    def _start_plot_progress(self, total: int) -> None:
        if self.plot_loading_dialog is not None:
            self.plot_loading_dialog.hide()
        self.plot_loading_dialog = QProgressDialog("Rendering plot...", "Cancel", 0, total, self)
        self.plot_loading_dialog.setWindowTitle("Rendering")
        self.plot_loading_dialog.setWindowModality(Qt.WindowModal)
        self.plot_loading_dialog.setCancelButtonText("Cancel")
        self.plot_loading_dialog.canceled.connect(self._cancel_plot)
        # ensure the dialog appears immediately and is responsive
        try:
            self.plot_loading_dialog.setMinimumDuration(0)
            self.plot_loading_dialog.setValue(0)
            self.plot_loading_dialog.setLabelText(f"Rendering plot... (0/{total})")
            self.plot_loading_dialog.show()
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
        except Exception:
            self.plot_loading_dialog.show()

    def _on_plot_progress(self, current: int, total: int) -> None:
        if self.plot_loading_dialog is None:
            return
        self.plot_loading_dialog.setRange(0, total)
        self.plot_loading_dialog.setValue(current)
        self.plot_loading_dialog.setLabelText(f"Rendering plot... ({current}/{total})")
        try:
            app = QApplication.instance()
            if app is not None:
                app.processEvents()
        except Exception:
            pass

    def _on_plot_complete(self) -> None:
        if self.plot_loading_dialog is not None:
            self.plot_loading_dialog.hide()
            self.plot_loading_dialog = None

    def _cancel_plot(self) -> None:
        if self.plot_loading_dialog is not None:
            self.plot_loading_dialog.hide()
            self.plot_loading_dialog = None
        if self.visualization._render_timer.isActive():
            self.visualization._render_timer.stop()

    def _apply_plot_filters(self, positions: list[dict]) -> None:
        try:
            self.visualization.render_all_positions = bool(getattr(self.settings, "render_all_positions", False))
            self.visualization.plot_positions(positions)
            if len(positions) > 500:
                self._start_plot_progress(len(positions))
        except Exception:
            try:
                self.visualization.plot_positions(positions[:5000])
                if len(positions) > 500:
                    self._start_plot_progress(min(len(positions), 5000))
            except Exception:
                pass

    def _show_all_positions(self) -> None:
        self.visualization.set_selected_norad(None)
        self.visualization.set_selected_history_orbits([])
        self.visualization.set_selected_last_position(None)
        self.visualization.render_all_positions = True
        self._apply_plot_filters(self.current_positions or [])
        self.statusBar().showMessage("Showing all plotted positions")

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings)
        if dialog.exec() == QDialog.Accepted:
            self.settings = dialog.settings
            self.settings_manager.save(self.settings)
            self.category_label.setText(f"Category: {self.settings.default_category}")
            self.visualization.show_debug_overlay = self.settings.show_debug_overlay
            self.apply_theme(self.settings.theme)
            self.statusBar().showMessage("Settings updated")
            self.log_dialog.append("Settings updated")
            self.refresh_object_list()

    def open_log(self) -> None:
        self.log_dialog.show()

    def open_database_manager(self) -> None:
        dlg = DatabaseDialog(self.database, self)
        dlg.exec()

    def open_about(self) -> None:
        dlg = AboutDialog(self, theme=self.settings.theme)
        dlg.exec()

    def open_licence(self) -> None:
        dlg = LicenseDialog(Path("Licence.txt"), self)
        dlg.exec()
