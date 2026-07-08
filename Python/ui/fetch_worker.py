from __future__ import annotations

import math
from typing import List

from PySide6.QtCore import QObject, Signal, Slot
from requests.exceptions import SSLError

import warnings
import requests
from urllib3.exceptions import InsecureRequestWarning

from data.fetcher import CelesTrakFetcher
from data.models import TrackedObject
from skyfield.api import load
from datetime import timedelta


class FetchWorker(QObject):
    finished = Signal(object)
    error = Signal(str, object)
    progress = Signal(str, int, int)

    def __init__(
        self,
        fetcher: CelesTrakFetcher,
        category: str,
        cached_objects: list[TrackedObject] | None = None,
        enabled_subgroups: list[str] | None = None,
    ) -> None:
        super().__init__()
        self.fetcher = fetcher
        self.category = category
        self.cached_objects = cached_objects
        self.enabled_subgroups = enabled_subgroups
        self._stopped = False

    def stop(self) -> None:
        """Request the worker to stop as soon as possible."""
        self._stopped = True

    @Slot()
    def run(self) -> None:
        try:
            objects: List[TrackedObject] = []

            if self.cached_objects is not None:
                objects = list(self.cached_objects)
                total_objects = len(objects)
                try:
                    self.progress.emit("process", 0, total_objects)
                except Exception:
                    pass
            else:
                groups_to_fetch = self.fetcher.build_groups_to_fetch(self.category, self.enabled_subgroups)
                total_urls = len(groups_to_fetch)
                try:
                    self.progress.emit("download", 0, total_urls)
                except Exception:
                    pass

                fetched_urls = 0
                for subgroup_key, url in groups_to_fetch.items():
                    if self._stopped:
                        break
                    with warnings.catch_warnings():
                        if not self.fetcher.verify_ssl:
                            warnings.simplefilter("ignore", InsecureRequestWarning)
                        response = requests.get(url, timeout=20, verify=self.fetcher.verify_ssl)
                    response.raise_for_status()
                    payload = response.json()
                    for item in payload:
                        try:
                            objects.append(TrackedObject.from_json(item, subgroup_key))
                        except ValueError:
                            continue
                    fetched_urls += 1
                    try:
                        self.progress.emit("download", fetched_urls, total_urls)
                    except Exception:
                        pass

            ts = load.timescale()
            now = ts.now()
            positions: list[dict] = []

            processed = 0
            total_proc = len(objects)
            try:
                self.progress.emit("process", 0, total_proc)
            except Exception:
                pass

            for obj in objects:
                if self._stopped:
                    payload = {"objects": objects, "positions": positions}
                    self.finished.emit(payload)
                    return
                try:
                    sat = obj.to_satellite()
                    sub = sat.at(now).subpoint()
                    lat = float(sub.latitude.degrees)
                    lon = float(sub.longitude.degrees)

                    try:
                        alt_km = float(sat.at(now).distance().km) - 6371.0
                    except Exception:
                        alt_km = 0.0

                    if math.isnan(lat) or math.isnan(lon) or math.isnan(alt_km):
                        continue

                    from math import acos, degrees

                    R = 6371.0
                    h = max(0.0, alt_km)
                    try:
                        ang = acos(R / (R + h))
                        footprint_deg = degrees(ang)
                    except Exception:
                        footprint_deg = 0.0

                    track_minutes_window = 90
                    track_steps = 60
                    base_dt = now.utc_datetime()
                    half_window_seconds = (track_minutes_window * 60) / 2.0
                    times = [
                        ts.utc(base_dt + timedelta(seconds=((i / track_steps) * track_minutes_window * 60) - half_window_seconds))
                        for i in range(track_steps + 1)
                    ]
                    ground_track: list[tuple[float, float]] = []
                    orbit_path: list[tuple[float, float, float]] = []
                    for t in times:
                        if self._stopped:
                            break
                        try:
                            point = sat.at(t)
                            subp = point.subpoint()
                            lat_deg = float(subp.latitude.degrees)
                            lon_deg = float(subp.longitude.degrees)
                            orbit_alt = max(0.0, float(point.distance().km) - R)
                            ground_track.append((lat_deg, lon_deg))
                            orbit_path.append((lat_deg, lon_deg, orbit_alt))
                        except Exception:
                            continue

                    positions.append({
                        "norad_id": obj.norad_id,
                        "name": obj.name,
                        "lat": lat,
                        "lon": lon,
                        "alt_km": alt_km,
                        "footprint_deg": footprint_deg,
                        "ground_track": ground_track,
                        "orbit_path": orbit_path,
                        "category": obj.category,
                    })

                    processed += 1
                    try:
                        self.progress.emit("process", processed, total_proc)
                    except Exception:
                        pass
                except Exception:
                    continue

            payload = {"objects": objects, "positions": positions}
            self.finished.emit(payload)
        except Exception as exc:
            self.error.emit(str(exc), exc)
