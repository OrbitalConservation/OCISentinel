from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from .models import TleHistoryRecord, TrackedObject

CREATE_OBJECT_TABLE = """
CREATE TABLE IF NOT EXISTS objects (
    norad_id INTEGER PRIMARY KEY,
    name TEXT,
    category TEXT,
    line1 TEXT,
    line2 TEXT,
    epoch TEXT,
    updated_at TEXT
)
"""

CREATE_TLE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS tle_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    norad_id INTEGER,
    fetch_time TEXT,
    line1 TEXT,
    line2 TEXT,
    source TEXT,
    UNIQUE(norad_id, line1, line2)
)
"""


class DatabaseManager:
    def __init__(self, path: Path):
        self.path = path
        self.connection = sqlite3.connect(str(self.path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.initialize()

    def initialize(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(CREATE_OBJECT_TABLE)
        cursor.execute(CREATE_TLE_HISTORY_TABLE)
        self.connection.commit()

    def upsert_object(self, obj: TrackedObject) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO objects (norad_id, name, category, line1, line2, epoch, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(norad_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                line1=excluded.line1,
                line2=excluded.line2,
                epoch=excluded.epoch,
                updated_at=CURRENT_TIMESTAMP
            """,
            (obj.norad_id, obj.name, obj.category, obj.line1, obj.line2, obj.epoch),
        )
        self.connection.commit()

    def upsert_objects(self, objs: Iterable[TrackedObject]) -> None:
        cursor = self.connection.cursor()
        params = [
            (o.norad_id, o.name, o.category, o.line1, o.line2, o.epoch) for o in objs
        ]
        cursor.executemany(
            """
            INSERT INTO objects (norad_id, name, category, line1, line2, epoch, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(norad_id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                line1=excluded.line1,
                line2=excluded.line2,
                epoch=excluded.epoch,
                updated_at=CURRENT_TIMESTAMP
            """,
            params,
        )
        self.connection.commit()

    def insert_tle_history(self, obj: TrackedObject, source: str = "celestrak") -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO tle_history (norad_id, fetch_time, line1, line2, source)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            (obj.norad_id, obj.line1, obj.line2, source),
        )
        self.connection.commit()

    def insert_tle_history_bulk(self, objs: Iterable[TrackedObject], source: str = "celestrak") -> None:
        cursor = self.connection.cursor()
        params = [(o.norad_id, o.line1, o.line2, source) for o in objs]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO tle_history (norad_id, fetch_time, line1, line2, source)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?)
            """,
            params,
        )
        self.connection.commit()

    def get_objects(self, norad_id: int | None = None, category: str | None = None, name: str | None = None) -> list[TrackedObject]:
        """Retrieve objects with optional filters.

        - norad_id: exact NORAD id match
        - category: exact category match (use 'all' or None to disable)
        - name: substring (case-insensitive) match against the object name
        """
        query = "SELECT * FROM objects"
        params: list[str] = []
        filters: list[str] = []

        if category and category != "all":
            filters.append("category = ?")
            params.append(category)

        if norad_id is not None:
            filters.append("norad_id = ?")
            params.append(str(norad_id))

        if name:
            filters.append("LOWER(name) LIKE ?")
            params.append(f"%{name.lower()}%")

        if filters:
            query += " WHERE " + " AND ".join(filters)

        query += " ORDER BY updated_at DESC"
        cursor = self.connection.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [TrackedObject.from_row(row) for row in rows]

    def get_object(self, norad_id: int) -> TrackedObject | None:
        cursor = self.connection.cursor()
        row = cursor.execute("SELECT * FROM objects WHERE norad_id = ?", (norad_id,)).fetchone()
        if not row:
            return None
        return TrackedObject.from_row(row)

    def get_tle_history_count(self, norad_id: int) -> int:
        cursor = self.connection.cursor()
        row = cursor.execute(
            "SELECT COUNT(*) AS count FROM tle_history WHERE norad_id = ?",
            (norad_id,),
        ).fetchone()
        return int(row[0]) if row is not None else 0

    def get_tle_history(self, norad_id: int) -> list[TleHistoryRecord]:
        cursor = self.connection.cursor()
        rows = cursor.execute(
            "SELECT norad_id, fetch_time, line1, line2, source FROM tle_history WHERE norad_id = ? ORDER BY fetch_time DESC",
            (norad_id,),
        ).fetchall()
        return [TleHistoryRecord.from_row(row) for row in rows]

    def delete_tle_history(self, norad_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM tle_history WHERE norad_id = ?", (norad_id,))
        self.connection.commit()

    def delete_object(self, norad_id: int) -> None:
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM objects WHERE norad_id = ?", (norad_id,))
        self.connection.commit()

    def get_latest_objects(self) -> list[TrackedObject]:
        return self.get_objects()

    def close(self) -> None:
        self.connection.close()
