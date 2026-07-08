from __future__ import annotations

from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import APP_ICON_PATH, AppSettings, CELESTRAK_DATA_GROUPS, DEFAULT_ENABLED_DATA_SUBGROUPS


class SettingsDialog(QDialog):
    def __init__(self, current_settings: AppSettings) -> None:
        super().__init__()
        self.setWindowTitle("Settings")
        self.setWindowIcon(QIcon(QPixmap(str(APP_ICON_PATH))))
        self.settings = AppSettings(**current_settings.to_dict())

        self.resize(980, 450)

        self.archive_checkbox = QCheckBox("Enable local tracking archive")
        self.archive_checkbox.setChecked(self.settings.archive_enabled)

        self.tle_history_checkbox = QCheckBox("Store TLE history")
        self.tle_history_checkbox.setChecked(self.settings.store_tle_history)

        self.position_history_checkbox = QCheckBox("Store position history")
        self.position_history_checkbox.setChecked(self.settings.store_position_history)

        self.auto_refresh_checkbox = QCheckBox("Automatic refresh")
        self.auto_refresh_checkbox.setChecked(self.settings.auto_refresh)

        self.startup_refresh_checkbox = QCheckBox("Refresh on startup")
        self.startup_refresh_checkbox.setChecked(self.settings.refresh_on_startup)

        self.frequency_input = QLineEdit(str(self.settings.update_frequency_minutes))

        self.show_debug_checkbox = QCheckBox("Show plot debug overlay")
        self.show_debug_checkbox.setChecked(self.settings.show_debug_overlay)
        self.render_all_checkbox = QCheckBox("Render all positions (may be slow)")
        try:
            self.render_all_checkbox.setChecked(self.settings.render_all_positions)
        except Exception:
            self.render_all_checkbox.setChecked(False)
        
        self.plot_subgroup_checkboxes: dict[str, QCheckBox] = {}
        self.offline_checkbox = QCheckBox("Offline mode")
        self.offline_checkbox.setChecked(self.settings.offline_mode)

        self.verify_ssl_checkbox = QCheckBox("Verify SSL certificates")
        self.verify_ssl_checkbox.setChecked(self.settings.verify_ssl)

        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "all",
            "fengyun-1c-debris",
            "iridium-33-debris",
            "cosmos-2251-debris",
        ])
        self.category_combo.setCurrentText(self.settings.default_category)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["light", "dark"])
        self.theme_combo.setCurrentText(self.settings.theme)

        self.subgroup_checkboxes: dict[str, QCheckBox] = {}
        self.plot_subgroup_checkboxes: dict[str, QCheckBox] = {}

        fetch_widget = QWidget()
        fetch_layout = QVBoxLayout(fetch_widget)
        fetch_layout.setContentsMargins(0, 0, 0, 0)
        fetch_layout.setSpacing(4)
        fetch_layout.addWidget(QLabel("Choose which CelesTrak subgroups are fetched: "))
        for top_group, submap in CELESTRAK_DATA_GROUPS.items():
            group_label = QLabel(f"<b>{top_group.capitalize()}</b>")
            fetch_layout.addWidget(group_label)
            for subgroup_key in submap:
                checkbox = QCheckBox(subgroup_key)
                checkbox.setChecked(subgroup_key in self.settings.enabled_data_subgroups)
                self.subgroup_checkboxes[subgroup_key] = checkbox
                fetch_layout.addWidget(checkbox)

        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        plot_layout.setContentsMargins(0, 0, 0, 0)
        plot_layout.setSpacing(4)
        plot_layout.addWidget(QLabel("Choose which subgroups are plotted: "))
        for top_group, submap in CELESTRAK_DATA_GROUPS.items():
            group_label = QLabel(f"<b>{top_group.capitalize()}</b>")
            plot_layout.addWidget(group_label)
            for subgroup_key in submap:
                checkbox = QCheckBox(subgroup_key)
                checkbox.setChecked(subgroup_key in getattr(self.settings, "enabled_plot_subgroups", DEFAULT_ENABLED_DATA_SUBGROUPS.copy()))
                self.plot_subgroup_checkboxes[subgroup_key] = checkbox
                plot_layout.addWidget(checkbox)

        fetch_scroll = QScrollArea()
        fetch_scroll.setWidgetResizable(True)
        fetch_scroll.setWidget(fetch_widget)
        fetch_scroll.setFixedHeight(180)

        plot_scroll = QScrollArea()
        plot_scroll.setWidgetResizable(True)
        plot_scroll.setWidget(plot_widget)
        plot_scroll.setFixedHeight(180)

        group_container = QWidget()
        group_layout = QHBoxLayout(group_container)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(10)
        group_layout.addWidget(fetch_scroll)
        group_layout.addWidget(plot_scroll)

        storage_group = QGroupBox("Data Storage")
        storage_layout = QVBoxLayout(storage_group)
        storage_layout.addWidget(self.archive_checkbox)
        storage_layout.addWidget(self.tle_history_checkbox)
        storage_layout.addWidget(self.position_history_checkbox)

        refresh_group = QGroupBox("Refresh Options")
        refresh_layout = QVBoxLayout(refresh_group)
        refresh_layout.addWidget(self.auto_refresh_checkbox)
        refresh_layout.addWidget(self.startup_refresh_checkbox)
        refresh_layout.addWidget(QLabel("Update frequency (minutes):"))
        refresh_layout.addWidget(self.frequency_input)
        refresh_layout.addWidget(self.offline_checkbox)
        refresh_layout.addWidget(self.verify_ssl_checkbox)

        visualization_group = QGroupBox("Visualization")
        visualization_layout = QVBoxLayout(visualization_group)
        visualization_layout.addWidget(self.show_debug_checkbox)
        visualization_layout.addWidget(self.render_all_checkbox)

        display_group = QGroupBox("Display & Filters")
        display_layout = QFormLayout(display_group)
        display_layout.addRow(QLabel("Default category:"), self.category_combo)
        display_layout.addRow(QLabel("Theme:"), self.theme_combo)

        group_panel = QWidget()
        group_panel_layout = QVBoxLayout(group_panel)
        group_panel_layout.setContentsMargins(0, 0, 0, 0)
        group_panel_layout.setSpacing(8)
        group_panel_layout.addWidget(QLabel("Fetch vs Plot Groups:"))
        group_panel_layout.addWidget(group_container)

        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        left_column.addWidget(storage_group)
        left_column.addWidget(refresh_group)
        left_column.addWidget(visualization_group)
        left_column.addStretch(1)

        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        right_column.addWidget(display_group)
        right_column.addWidget(group_panel)
        right_column.addStretch(1)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(16)
        main_layout.addLayout(left_column, 1)
        main_layout.addLayout(right_column, 1)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        outer_layout = QVBoxLayout()
        outer_layout.addLayout(main_layout)
        outer_layout.addWidget(button_box)
        self.setLayout(outer_layout)

        self._subgroup_checkboxes = self.subgroup_checkboxes

    def accept(self) -> None:
        self.settings.archive_enabled = self.archive_checkbox.isChecked()
        self.settings.store_tle_history = self.tle_history_checkbox.isChecked()
        self.settings.store_position_history = self.position_history_checkbox.isChecked()
        self.settings.auto_refresh = self.auto_refresh_checkbox.isChecked()
        self.settings.offline_mode = self.offline_checkbox.isChecked()
        self.settings.verify_ssl = self.verify_ssl_checkbox.isChecked()
        self.settings.default_category = cast(str, self.category_combo.currentText())
        self.settings.theme = cast(str, self.theme_combo.currentText())
        self.settings.refresh_on_startup = self.startup_refresh_checkbox.isChecked()
        try:
            self.settings.update_frequency_minutes = int(self.frequency_input.text())
        except ValueError:
            self.settings.update_frequency_minutes = 30
        self.settings.show_debug_overlay = self.show_debug_checkbox.isChecked()
        try:
            self.settings.render_all_positions = self.render_all_checkbox.isChecked()
        except Exception:
            self.settings.render_all_positions = False
        self.settings.enabled_data_subgroups = [
            subgroup for subgroup, checkbox in self._subgroup_checkboxes.items() if checkbox.isChecked()
        ]
        if not self.settings.enabled_data_subgroups:
            self.settings.enabled_data_subgroups = [
                subgroup
                for submap in CELESTRAK_DATA_GROUPS.values()
                for subgroup in submap.keys()
            ]
        self.settings.enabled_plot_subgroups = [
            subgroup for subgroup, checkbox in self.plot_subgroup_checkboxes.items() if checkbox.isChecked()
        ]
        if not self.settings.enabled_plot_subgroups:
            self.settings.enabled_plot_subgroups = [
                subgroup
                for submap in CELESTRAK_DATA_GROUPS.values()
                for subgroup in submap.keys()
            ]
        super().accept()
