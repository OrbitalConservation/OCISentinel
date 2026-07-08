from __future__ import annotations

import math
from typing import Iterable

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtGui import QPolygonF
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QSizePolicy, QWidget


class VisualizationWidget(QWidget):
    plot_progress = Signal(int, int)
    plot_complete = Signal()
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.positions: list[dict] = []
        self.selected_norad: int | None = None
        self.selected_history_orbits: list[list[tuple[float, float, float]]] = []
        self.selected_last_position: dict | None = None
        self.stats: dict = {"fetched": 0, "positions": 0}
        self.rotation_angle = 0.0
        self.show_debug_overlay = True

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._advance_rotation)
        self.animation_timer.start(60)

        self.render_all_positions: bool = False
        self.max_render_points: int = 5000
        self._full_positions: list[dict] = []
        self._render_index: int = 0
        self._render_batch_size: int = 500
        self._render_timer = QTimer(self)
        self._render_timer.timeout.connect(self._render_batch)
        self._render_batch_counter: int = 0

    def _advance_rotation(self) -> None:
        self.rotation_angle += math.radians(0.6)
        if self.rotation_angle >= math.tau:
            self.rotation_angle -= math.tau
        self.update()

    def set_selected_history_orbits(self, orbits: list[list[tuple[float, float, float]]]) -> None:
        self.selected_history_orbits = orbits
        self.update()

    def set_selected_last_position(self, position: dict | None) -> None:
        self.selected_last_position = position
        self.update()

    def _project_geo_point(self, lat: float, lon: float, center_x: float, center_y: float, radius: float, alt_km: float = 0.0) -> tuple[float, float, bool]:
        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)

        x = math.cos(lat_rad) * math.cos(lon_rad)
        y = math.sin(lat_rad)
        z = math.cos(lat_rad) * math.sin(lon_rad)

        cos_a = math.cos(self.rotation_angle)
        sin_a = math.sin(self.rotation_angle)
        xr = x * cos_a - z * sin_a
        zr = x * sin_a + z * cos_a

        alt_factor = min(max(alt_km / 1000.0, 0.0), 1.2)
        scaled_radius = radius * (1.0 + alt_factor * 0.18)

        screen_x = center_x + xr * scaled_radius
        screen_y = center_y - y * scaled_radius
        return screen_x, screen_y, zr >= 0

    def _angular_gap_deg(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
        return math.degrees(c)

    def _draw_ground_track(self, painter: QPainter, track: list[tuple[float, float]], center_x: float, center_y: float, radius: float) -> None:
        painter.setPen(QPen(QColor(255, 220, 120, 220), 3, Qt.DashLine))
        segment = QPolygonF()
        prev_lat: float | None = None
        prev_lon: float | None = None
        for lat, lon in track:
            if math.isnan(lat) or math.isnan(lon):
                if len(segment) >= 2:
                    painter.drawPolyline(segment)
                segment = QPolygonF()
                prev_lat = None
                prev_lon = None
                continue
            x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius)
            if not visible:
                if len(segment) >= 2:
                    painter.drawPolyline(segment)
                segment = QPolygonF()
                prev_lat = None
                prev_lon = None
                continue
            if prev_lat is not None and prev_lon is not None:
                raw_lon_diff = abs(lon - prev_lon)
                lon_diff = min(raw_lon_diff, 360.0 - raw_lon_diff)
                if lon_diff > 120:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
                gap_deg = self._angular_gap_deg(prev_lat, prev_lon, lat, lon)
                if gap_deg > 35.0:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
                
                if (abs(prev_lat) > 80.0 or abs(lat) > 80.0) and lon_diff > 35.0:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
            if len(segment) >= 1:
                prev = segment[-1]
                dx = x - prev.x()
                dy = y - prev.y()
                if dx * dx + dy * dy > (radius * 0.55) ** 2:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
            segment.append(QPointF(x, y))
            prev_lat = lat
            prev_lon = lon
        if len(segment) >= 2:
            painter.drawPolyline(segment)

    def _draw_orbit_path(self, painter: QPainter, path: list[tuple[float, float, float]], center_x: float, center_y: float, radius: float) -> None:
        painter.setPen(QPen(QColor(255, 180, 80, 180), 2, Qt.SolidLine))
        segment = QPolygonF()
        prev_lat: float | None = None
        prev_lon: float | None = None
        for lat, lon, alt in path:
            if math.isnan(lat) or math.isnan(lon) or math.isnan(alt):
                if len(segment) >= 2:
                    painter.drawPolyline(segment)
                segment = QPolygonF()
                prev_lat = None
                prev_lon = None
                continue
            alt_factor = min(max((alt + 200.0) / 2200.0, 0.0), 1.0)
            x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius + alt_factor * radius * 0.15)
            if not visible:
                if len(segment) >= 2:
                    painter.drawPolyline(segment)
                segment = QPolygonF()
                prev_lat = None
                prev_lon = None
                continue
            if prev_lat is not None and prev_lon is not None:
                raw_lon_diff = abs(lon - prev_lon)
                lon_diff = min(raw_lon_diff, 360.0 - raw_lon_diff)
                if lon_diff > 120:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
                gap_deg = self._angular_gap_deg(prev_lat, prev_lon, lat, lon)
                if gap_deg > 35.0:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
                
                if (abs(prev_lat) > 80.0 or abs(lat) > 80.0) and lon_diff > 35.0:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
            if len(segment) >= 1:
                prev = segment[-1]
                dx = x - prev.x()
                dy = y - prev.y()
                if dx * dx + dy * dy > (radius * 0.65) ** 2:
                    if len(segment) >= 2:
                        painter.drawPolyline(segment)
                    segment = QPolygonF()
            segment.append(QPointF(x, y))
            prev_lat = lat
            prev_lon = lon
        if len(segment) >= 2:
            painter.drawPolyline(segment)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        center_x = width / 2
        center_y = height / 2
        radius = min(width, height) * 0.35

        painter.fillRect(0, 0, width, height, QColor(10, 18, 34))

        painter.setBrush(QColor(15, 30, 80, 220))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        wire_pen = QPen(QColor(140, 190, 255, 180), 1)
        painter.setPen(wire_pen)
        painter.setBrush(Qt.NoBrush)
        for lat in range(-75, 90, 15):
            segment = QPolygonF()
            for lon in range(0, 361, 10):
                x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius)
                if not visible and len(segment) >= 2:
                    painter.drawPolyline(segment)
                    segment = QPolygonF()
                    continue
                segment.append(QPointF(x, y))
            if len(segment) >= 2:
                painter.drawPolyline(segment)

        for lon in range(0, 360, 30):
            segment = QPolygonF()
            for lat in range(-85, 86, 10):
                x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius)
                if not visible and len(segment) >= 2:
                    painter.drawPolyline(segment)
                    segment = QPolygonF()
                    continue
                segment.append(QPointF(x, y))
            if len(segment) >= 2:
                painter.drawPolyline(segment)

        earth_pen = QPen(QColor(120, 200, 255, 220), 2)
        painter.setPen(earth_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(center_x - radius, center_y - radius, radius * 2, radius * 2)

        pole_pen = QPen(QColor(255, 255, 255), 2)
        painter.setPen(pole_pen)
        painter.drawLine(int(center_x), int(center_y - radius), int(center_x), int(center_y - radius + 16))
        painter.drawLine(int(center_x), int(center_y + radius), int(center_x), int(center_y + radius - 16))

        selected_pos = None
        for pos in self.positions:
            try:
                if self.selected_norad is not None:
                    try:
                        if int(pos.get("norad_id", -1)) == int(self.selected_norad):
                            selected_pos = pos
                            break
                    except Exception:
                        if str(pos.get("norad_id", "")).strip() == str(self.selected_norad).strip():
                            selected_pos = pos
                            break
            except Exception:
                continue

        if self.selected_norad is not None and selected_pos is None and self.selected_last_position is not None:
            selected_pos = self.selected_last_position

        point_radius = 5
        painter.setBrush(Qt.NoBrush)

        for pos in self.positions:
            try:
                if selected_pos is not None:
                    try:
                        if int(pos.get("norad_id", -1)) == int(selected_pos.get("norad_id", -1)):
                            continue
                    except Exception:
                        if str(pos.get("norad_id", "")).strip() == str(selected_pos.get("norad_id", "")).strip():
                            continue

                lon = float(pos.get("lon", 0.0))
                lat = float(pos.get("lat", 0.0))
                alt_km = float(pos.get("alt_km", 0.0))
                x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius, alt_km)
                if math.isnan(x) or math.isnan(y):
                    continue

                cat = str(pos.get("category", "")).lower()
                if "active" in cat:
                    color_fill = QColor(140, 255, 140, 220)
                    outline = QColor(100, 220, 120, 200)
                else:
                    color_fill = QColor(205, 235, 255, 240)
                    outline = QColor(255, 255, 255, 120)

                if visible:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(color_fill)
                    painter.drawEllipse(int(x) - point_radius, int(y) - point_radius, point_radius * 2, point_radius * 2)
                    painter.setPen(QPen(outline, 1))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(int(x) - point_radius, int(y) - point_radius, point_radius * 2, point_radius * 2)
                else:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(150, 175, 200, 120))
                    painter.drawEllipse(int(x) - (point_radius - 1), int(y) - (point_radius - 1), (point_radius - 1) * 2, (point_radius - 1) * 2)
            except Exception:
                continue

        if selected_pos is not None:
            try:
                lon = float(selected_pos.get("lon", 0.0))
                lat = float(selected_pos.get("lat", 0.0))
                alt_km = float(selected_pos.get("alt_km", 0.0))
                x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius, alt_km)
                if not (math.isnan(x) or math.isnan(y)):
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QColor(255, 215, 100, 220))
                    painter.drawEllipse(int(x) - 9, int(y) - 9, 18, 18)
                    painter.setPen(QPen(QColor(255, 220, 140, 220), 3))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(int(x) - 12, int(y) - 12, 24, 24)
            except Exception:
                pass

        if self.selected_history_orbits:
            try:
                cat = str(selected_pos.get("category", "")).lower() if selected_pos is not None else ""
            except Exception:
                cat = ""
            if "active" in cat:
                history_pen = QPen(QColor(120, 250, 140, 180), 2, Qt.DashLine)
            else:
                history_pen = QPen(QColor(120, 250, 255, 180), 2, Qt.DashLine)
            for orbit in self.selected_history_orbits:
                segment = QPolygonF()
                prev_hist_lat: float | None = None
                prev_hist_lon: float | None = None
                for lat, lon, alt in orbit:
                    if math.isnan(lat) or math.isnan(lon) or math.isnan(alt):
                        if len(segment) >= 2:
                            painter.setPen(history_pen)
                            painter.drawPolyline(segment)
                        segment = QPolygonF()
                        prev_hist_lat = None
                        prev_hist_lon = None
                        continue
                    alt_factor = min(max((alt + 200.0) / 2200.0, 0.0), 1.0)
                    x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius + alt_factor * radius * 0.15)
                    if not visible:
                        if len(segment) >= 2:
                            painter.setPen(history_pen)
                            painter.drawPolyline(segment)
                        segment = QPolygonF()
                        prev_hist_lat = None
                        prev_hist_lon = None
                        continue
                    if prev_hist_lat is not None and prev_hist_lon is not None:
                        raw_hist_lon = abs(lon - prev_hist_lon)
                        hist_lon_diff = min(raw_hist_lon, 360.0 - raw_hist_lon)
                        gap_deg = self._angular_gap_deg(prev_hist_lat, prev_hist_lon, lat, lon)
                        if gap_deg > 35.0:
                            if len(segment) >= 2:
                                painter.setPen(history_pen)
                                painter.drawPolyline(segment)
                            segment = QPolygonF()
                        if (abs(prev_hist_lat) > 80.0 or abs(lat) > 80.0) and hist_lon_diff > 35.0:
                            if len(segment) >= 2:
                                painter.setPen(history_pen)
                                painter.drawPolyline(segment)
                            segment = QPolygonF()
                    segment.append(QPointF(x, y))
                    prev_hist_lat = lat
                    prev_hist_lon = lon
                if len(segment) >= 2:
                    painter.setPen(history_pen)
                    painter.drawPolyline(segment)

        if self.selected_last_position is not None and selected_pos is None:
            try:
                lon = float(self.selected_last_position.get("lon", 0.0))
                lat = float(self.selected_last_position.get("lat", 0.0))
                x, y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius)
                if visible and not (math.isnan(x) or math.isnan(y)):
                    painter.setPen(QPen(QColor(120, 255, 255, 220), 3))
                    painter.drawEllipse(int(x) - 6, int(y) - 6, 12, 12)
                    painter.setPen(QPen(QColor(120, 255, 255, 120), 1, Qt.DashLine))
                    painter.drawEllipse(int(x) - 12, int(y) - 12, 24, 24)
            except Exception:
                pass

        if selected_pos is not None:
            path = selected_pos.get("orbit_path") or []
            if len(path) >= 2:
                self._draw_orbit_path(painter, path, center_x, center_y, radius)

            track = selected_pos.get("ground_track") or []
            if len(track) >= 2:
                self._draw_ground_track(painter, track, center_x, center_y, radius)

            try:
                lon = float(selected_pos.get("lon", 0.0))
                lat = float(selected_pos.get("lat", 0.0))
            except Exception:
                lon = 0.0
                lat = 0.0

            sel_x, sel_y, visible = self._project_geo_point(lat, lon, center_x, center_y, radius)
            if visible and not (math.isnan(sel_x) or math.isnan(sel_y)):
                painter.setPen(QPen(QColor(255, 180, 80, 180), 2, Qt.DashLine))
                painter.drawEllipse(int(sel_x) - 10, int(sel_y) - 10, 20, 20)

        if self.show_debug_overlay:
            painter.setPen(QPen(QColor(255, 255, 255), 1))
            painter.drawText(12, 20, f"Objects: {len(self.positions)}")
            painter.drawText(12, 35, "Wireframe Earth projection")

            hud_x = 12
            hud_y = height - 42
            painter.setPen(QPen(QColor(220, 220, 220), 1))
            painter.drawText(hud_x, hud_y, f"Fetched: {self.stats.get('fetched', 0)}")
            painter.drawText(hud_x, hud_y + 14, f"Positions: {self.stats.get('positions', 0)}")
            sel = self.selected_norad if self.selected_norad is not None else "-"
            painter.drawText(hud_x, hud_y + 28, f"Selected NORAD: {sel}")

    def _is_valid_position(self, position: dict) -> bool:
        try:
            lat = float(position.get("lat", float("nan")))
            lon = float(position.get("lon", float("nan")))
            if math.isnan(lat) or math.isnan(lon):
                return False
            return True
        except Exception:
            return False

    def plot_positions(self, positions: Iterable[dict]) -> None:
        pos_list = [position for position in positions if self._is_valid_position(position)]
        self._full_positions = pos_list
        self._render_index = 0

        selected_position: dict | None = None
        if self.selected_norad is not None:
            for position in pos_list:
                try:
                    if int(position.get("norad_id", -1)) == int(self.selected_norad):
                        selected_position = position
                        break
                except Exception:
                    if str(position.get("norad_id", "")).strip() == str(self.selected_norad).strip():
                        selected_position = position
                        break

        if not self.render_all_positions and len(self._full_positions) > self.max_render_points:
            step = max(1, len(self._full_positions) // self.max_render_points)
            self._full_positions = self._full_positions[::step]
            if selected_position is not None and selected_position not in self._full_positions:
                self._full_positions.append(selected_position)

        remaining = len(self._full_positions)
        self._render_batch_size = max(100, min(800, remaining // 30))
        
        self.positions = []
        self.stats["positions"] = 0
        if self._render_timer.isActive():
            self._render_timer.stop()
        if self._full_positions:
            self._render_timer.start(25)
        else:
            self.update()

    def _render_batch(self) -> None:
        if self._render_index >= len(self._full_positions):
            self._render_timer.stop()
            self.plot_complete.emit()
            return
        end = min(self._render_index + self._render_batch_size, len(self._full_positions))
        self.positions.extend(self._full_positions[self._render_index:end])
        self._render_index = end
        self.stats["positions"] = len(self.positions)
        self._render_batch_counter += 1
        if self._render_batch_counter % 5 == 0 or self._render_index >= len(self._full_positions):
            try:
                self.plot_progress.emit(self._render_index, len(self._full_positions))
            except Exception:
                pass
            self.update()

    def set_stats(self, fetched: int, positions: int) -> None:
        self.stats["fetched"] = fetched
        self.stats["positions"] = positions
        self.update()

    def set_selected_norad(self, norad_id: int | None) -> None:
        self.selected_norad = norad_id
        self.update()
