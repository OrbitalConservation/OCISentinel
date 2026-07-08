from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlite3 import Row
from typing import Tuple

from skyfield.api import EarthSatellite, load
from skyfield.api import wgs84


@dataclass
class TleHistoryRecord:
    norad_id: int
    fetch_time: str
    line1: str
    line2: str
    source: str

    @classmethod
    def from_row(cls, row: Row) -> "TleHistoryRecord":
        return cls(
            norad_id=int(row["norad_id"]),
            fetch_time=str(row["fetch_time"]),
            line1=str(row["line1"]),
            line2=str(row["line2"]),
            source=str(row["source"]),
        )


@dataclass
class TrackedObject:
    name: str
    norad_id: int
    category: str
    line1: str
    line2: str
    epoch: str

    @classmethod
    def from_tle(cls, name: str, line1: str, line2: str, category: str) -> "TrackedObject":
        if len(line1) < 69 or len(line2) < 69:
            raise ValueError("Invalid TLE format")
        norad_id = int(line1[2:7])
        epoch = line1[18:32].strip()
        return cls(name=name, norad_id=norad_id, category=category, line1=line1, line2=line2, epoch=epoch)

    @classmethod
    def from_json(cls, payload: dict[str, object], category: str) -> "TrackedObject":
        norad_id = int(payload.get("NORAD_CAT_ID", 0) or 0)
        if norad_id <= 0:
            raise ValueError("Missing NORAD ID")

        name = str(payload.get("OBJECT_NAME", "Unknown")).strip() or f"NORAD {norad_id}"
        epoch = str(payload.get("EPOCH", "")).strip()

        def _to_float(key: str, default: float = 0.0) -> float:
            try:
                return float(payload.get(key, default) or default)
            except Exception:
                return default

        mean_motion = _to_float("MEAN_MOTION")
        eccentricity = _to_float("ECCENTRICITY")
        inclination = _to_float("INCLINATION")
        raan = _to_float("RA_OF_ASC_NODE")
        arg_perigee = _to_float("ARG_OF_PERICENTER")
        mean_anomaly = _to_float("MEAN_ANOMALY")

        # Prefer explicit TLE lines if present in the JSON feed
        tle1 = payload.get("TLE_LINE1") or payload.get("TLE1") or payload.get("TLE_LINE_1")
        tle2 = payload.get("TLE_LINE2") or payload.get("TLE2") or payload.get("TLE_LINE_2")
        if isinstance(tle1, str) and isinstance(tle2, str) and len(tle1.strip()) >= 69 and len(tle2.strip()) >= 69:
            line1 = tle1.strip()
            line2 = tle2.strip()
        else:
            tle_epoch = cls._format_tle_epoch(epoch)
            if tle_epoch is None:
                raise ValueError("Missing or invalid epoch for TLE fallback")

            line1_body = f"1 {norad_id:05d}U 00000A {tle_epoch}  .00000000  00000-0  00000-0 0  999"
            line1 = line1_body.ljust(68)[:68] + cls._checksum(line1_body.ljust(68)[:68])

            line2_body = (
                f"2 {norad_id:05d} {inclination:8.4f} {raan:8.4f} {eccentricity:7.7f} "
                f"{arg_perigee:8.4f} {mean_anomaly:8.4f} {mean_motion:11.8f}    0"
            )
            line2 = line2_body.ljust(68)[:68] + cls._checksum(line2_body.ljust(68)[:68])

        ts = load.timescale()
        try:
            EarthSatellite(line1, line2, name, ts)
        except Exception as exc:
            raise ValueError(f"Invalid JSON TLE payload or fallback: {exc}") from exc

        return cls(name=name, norad_id=norad_id, category=category, line1=line1, line2=line2, epoch=epoch)

    @staticmethod
    def _format_tle_epoch(epoch: str) -> str | None:
        if not epoch:
            return None
        try:
            if isinstance(epoch, str) and "T" in epoch:
                parsed = datetime.fromisoformat(epoch)
            else:
                parsed = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            try:
                parsed = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    parsed = datetime.strptime(epoch, "%Y-%m-%d")
                except Exception:
                    return None

        year_short = parsed.year % 100
        day_of_year = parsed.timetuple().tm_yday
        seconds_in_day = parsed.hour * 3600 + parsed.minute * 60 + parsed.second + parsed.microsecond / 1_000_000
        fraction = seconds_in_day / 86400.0
        return f"{year_short:02d}{day_of_year:03d}.{fraction:08.8f}"

    @staticmethod
    def _checksum(line: str) -> str:
        checksum = 0
        for char in line[:68]:
            if char.isdigit():
                checksum += int(char)
            elif char == "-":
                checksum += 1
        return str(checksum % 10)

    @classmethod
    def from_row(cls, row: Row) -> "TrackedObject":
        return cls(
            name=row["name"],
            norad_id=row["norad_id"],
            category=row["category"],
            line1=row["line1"],
            line2=row["line2"],
            epoch=row["epoch"],
        )

    def to_satellite(self) -> EarthSatellite:
        ts = load.timescale()
        return EarthSatellite(self.line1, self.line2, self.name, ts)

    @staticmethod
    def _format_tle_epoch(epoch: str) -> str | None:
        if not epoch:
            return None
        try:
            if "T" in epoch:
                parsed = datetime.fromisoformat(epoch)
            else:
                parsed = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S.%f")
        except Exception:
            try:
                parsed = datetime.strptime(epoch, "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    parsed = datetime.strptime(epoch, "%Y-%m-%d")
                except Exception:
                    return None

        year_short = parsed.year % 100
        day_of_year = parsed.timetuple().tm_yday
        seconds_in_day = parsed.hour * 3600 + parsed.minute * 60 + parsed.second + parsed.microsecond / 1_000_000
        fraction = seconds_in_day / 86400.0
        return f"{year_short:02d}{day_of_year:03d}.{fraction:08.8f}"

    @staticmethod
    def _checksum(line: str) -> str:
        checksum = 0
        for char in line[:68]:
            if char.isdigit():
                checksum += int(char)
            elif char == "-":
                checksum += 1
        return str(checksum % 10)

    def propagate_positions(self, minutes: int = 120, steps: int = 120) -> tuple[list[float], list[float]]:
        sat = self.to_satellite()
        now = datetime.utcnow()
        end = now + timedelta(minutes=minutes)
        times = [now + (end - now) * i / max(steps - 1, 1) for i in range(steps)]
        ts = load.timescale()
        sky_times = ts.utc(times)
        geocentric = sat.at(sky_times)
        subpoints = geocentric.subpoint()
        latitudes = [float(lat.degrees) for lat in subpoints.latitude]
        longitudes = [float(lon.degrees) for lon in subpoints.longitude]
        return latitudes, longitudes

    def _linear_range(self, start: datetime, end: datetime, steps: int) -> list[float]:
        if steps <= 1:
            return [start.hour + start.minute / 60.0]
        delta = (end - start) / (steps - 1)
        values: list[float] = []
        current = start
        for _ in range(steps):
            values.append(current.hour + current.minute / 60.0 + current.second / 3600.0)
            current += delta
        return values
