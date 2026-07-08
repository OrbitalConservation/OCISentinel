from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_FILE = BASE_DIR / "data" / "oci_sentinel.db"
SETTINGS_FILE = BASE_DIR / "data" / "settings.json"
APP_NAME = "OCI Sentinel"
APP_VERSION = "1.1.1"
APP_ICON_PATH = BASE_DIR / "assets" / "oci_sentinel.png"
DATA_PULLS_PER_DAY = 10

CELESTRAK_RATE_LIMIT = int(DATA_PULLS_PER_DAY / 1440)

CELESTRAK_DATA_GROUPS = {
    "debris": {
        "fengyun-1c-debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=fengyun-1c-debris&FORMAT=json",
        "iridium-33-debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-33-debris&FORMAT=json",
        "cosmos-2251-debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=cosmos-2251-debris&FORMAT=json",
    },
    "active": {
        "active-satellites": "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=json",
    },
}

CELESTRAK_GROUP_URLS = {
    "fengyun-1c-debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=fengyun-1c-debris&FORMAT=json",
    "iridium-33-debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=iridium-33-debris&FORMAT=json",
    "cosmos-2251-debris": "https://celestrak.org/NORAD/elements/gp.php?GROUP=cosmos-2251-debris&FORMAT=json",
}

DEFAULT_ENABLED_DATA_SUBGROUPS = [
    subgroup
    for submap in CELESTRAK_DATA_GROUPS.values()
    for subgroup in submap.keys()
]

DEFAULT_SETTINGS = {
    "archive_enabled": True,
    "store_tle_history": True,
    "store_position_history": False,
    "auto_refresh": False,
    "update_frequency_minutes": CELESTRAK_RATE_LIMIT,
    "offline_mode": False,
    "default_category": "all",
    "theme": "light",
    "verify_ssl": True,
    "enabled_data_subgroups": DEFAULT_ENABLED_DATA_SUBGROUPS.copy(),
    "enabled_plot_subgroups": DEFAULT_ENABLED_DATA_SUBGROUPS.copy(),
    "render_all_positions": False,
}


@dataclass
class AppSettings:
    archive_enabled: bool = True
    store_tle_history: bool = True
    store_position_history: bool = False
    auto_refresh: bool = False
    refresh_on_startup: bool = False
    update_frequency_minutes: int = CELESTRAK_RATE_LIMIT
    offline_mode: bool = False
    default_category: str = "all"
    theme: str = "light"
    verify_ssl: bool = True
    show_debug_overlay: bool = True
    enabled_data_subgroups: list[str] = field(default_factory=lambda: DEFAULT_ENABLED_DATA_SUBGROUPS.copy())
    enabled_plot_subgroups: list[str] = field(default_factory=lambda: DEFAULT_ENABLED_DATA_SUBGROUPS.copy())
    render_all_positions: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        return cls(
            archive_enabled=data.get("archive_enabled", True),
            store_tle_history=data.get("store_tle_history", True),
            store_position_history=data.get("store_position_history", False),
            auto_refresh=data.get("auto_refresh", False),
            refresh_on_startup=data.get("refresh_on_startup", True),
            update_frequency_minutes=int(data.get("update_frequency_minutes", 30)),
            offline_mode=data.get("offline_mode", False),
            default_category=data.get("default_category", "all"),
            theme=data.get("theme", "light"),
            verify_ssl=data.get("verify_ssl", True),
            show_debug_overlay=data.get("show_debug_overlay", True),
            enabled_data_subgroups=data.get("enabled_data_subgroups", DEFAULT_ENABLED_DATA_SUBGROUPS.copy()),
            enabled_plot_subgroups=data.get("enabled_plot_subgroups", DEFAULT_ENABLED_DATA_SUBGROUPS.copy()),
            render_all_positions=data.get("render_all_positions", False),
        )


class SettingsManager:
    def __init__(self, path: Path = SETTINGS_FILE):
        self.path = path
        self.settings = AppSettings()

    def load(self) -> AppSettings:
        if not self.path.exists():
            self.save(self.settings)
            return self.settings

        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
                self.settings = AppSettings.from_dict(raw)
        except (json.JSONDecodeError, OSError):
            self.settings = AppSettings()
            self.save(self.settings)

        return self.settings

    def save(self, settings: AppSettings | None = None) -> AppSettings:
        if settings is not None:
            self.settings = settings
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump(self.settings.to_dict(), handle, indent=2)
        return self.settings
