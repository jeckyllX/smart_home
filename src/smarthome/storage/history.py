"""
SQLite time-series storage for room psychrometrics, device telemetry, and event history.
Uses Python's built-in sqlite3 in WAL mode with zero external dependencies.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from smarthome.core.events import (
    CommandDispatchedEvent,
    DeviceStateChangedEvent,
    Event,
    EventBus,
)

logger = logging.getLogger("TelemetryStore")


def _aggregate_bool_flag(values: list[bool | None]) -> bool | None:
    if any(v is True for v in values):
        return True
    if any(v is False for v in values):
        return False
    return None


class TelemetryStore:
    """
    Thread-safe SQLite store recording room climate snapshots and device events.
    """

    def __init__(self, db_path: str | Path = ":memory:", retention_days: int = 7):
        self.db_path = str(db_path)
        self.retention_days = max(1, retention_days)
        self._lock = threading.RLock()
        self._last_prune: float = 0.0
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            if self.db_path != ":memory:":
                cur.execute("PRAGMA journal_mode=WAL;")
                cur.execute("PRAGMA synchronous=NORMAL;")

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS room_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    room TEXT NOT NULL,
                    indoor_temp_c REAL,
                    indoor_rh REAL,
                    outdoor_temp_c REAL,
                    dew_point_c REAL,
                    safe_dew_point_c REAL,
                    target_rh INTEGER,
                    is_on INTEGER,
                    is_defrost INTEGER
                );
                """
            )
            cols = {row[1] for row in cur.execute("PRAGMA table_info(room_history)").fetchall()}
            if "is_defrost" not in cols:
                cur.execute("ALTER TABLE room_history ADD COLUMN is_defrost INTEGER;")
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_room_history_room_ts
                ON room_history (room, timestamp);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS device_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    device_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail TEXT NOT NULL
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_device_events_ts
                ON device_events (timestamp);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._conn.commit()

    def attach_event_bus(self, event_bus: EventBus) -> None:
        """Subscribe to state change and command events on the application EventBus."""
        event_bus.subscribe(DeviceStateChangedEvent, self._on_event)
        event_bus.subscribe(CommandDispatchedEvent, self._on_event)

    def _on_event(self, event: Event) -> None:
        try:
            if isinstance(event, DeviceStateChangedEvent):
                detail = json.dumps(
                    {
                        "trait": event.trait_name,
                        "property": event.property_name,
                        "old": event.old_value,
                        "new": event.new_value,
                    }
                )
                self.record_device_event(
                    device_id=event.device_id,
                    event_type="state_changed",
                    detail=detail,
                    timestamp=event.timestamp,
                )
            elif isinstance(event, CommandDispatchedEvent):
                detail = json.dumps(
                    {
                        "command": event.command,
                        "arguments": event.arguments,
                        "success": event.success,
                    }
                )
                self.record_device_event(
                    device_id=event.device_id,
                    event_type="command_dispatched",
                    detail=detail,
                    timestamp=event.timestamp,
                )
        except Exception as e:
            logger.warning("Failed to record event to SQLite: %s", e)

    def record_device_event(
        self,
        device_id: str,
        event_type: str,
        detail: str,
        timestamp: float | None = None,
    ) -> None:
        ts = timestamp if timestamp is not None else time.time()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO device_events (timestamp, device_id, event_type, detail)
                VALUES (?, ?, ?, ?)
                """,
                (ts, device_id, event_type, detail),
            )
            self._conn.commit()

    def record_room_snapshot(
        self,
        room: str,
        status: dict[str, Any],
        is_on: bool | None = None,
        is_defrost: bool | None = None,
        timestamp: float | None = None,
    ) -> None:
        """Record a periodic room climate and psychrometric snapshot."""
        ts = timestamp if timestamp is not None else time.time()
        is_on_int = None if is_on is None else (1 if is_on else 0)
        is_defrost_int = None if is_defrost is None else (1 if is_defrost else 0)

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO room_history (
                    timestamp, room, indoor_temp_c, indoor_rh,
                    outdoor_temp_c, dew_point_c, safe_dew_point_c,
                    target_rh, is_on, is_defrost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    room,
                    status.get("indoor_temp_c"),
                    status.get("indoor_rh_percent"),
                    status.get("effective_outdoor_c"),
                    status.get("dew_point_c"),
                    status.get("safe_dew_point_c"),
                    status.get("safe_target_rh"),
                    is_on_int,
                    is_defrost_int,
                ),
            )
            self._conn.commit()

            # Periodically prune old records (at most once per hour)
            if (ts - self._last_prune) > 3600.0:
                self._last_prune = ts
                self.prune_old_records(self.retention_days, now_ts=ts)

    def get_room_history(
        self,
        room: str,
        hours: float = 24.0,
        max_points: int = 180,
        now_ts: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query historical snapshots for a room over the past `hours`,
        downsampling evenly if the row count exceeds `max_points`.
        """
        now = now_ts if now_ts is not None else time.time()
        cutoff = now - (max(0.1, hours) * 3600.0)

        with self._lock:
            cur = self._conn.execute(
                """
                SELECT timestamp, indoor_temp_c, indoor_rh, outdoor_temp_c,
                       dew_point_c, safe_dew_point_c, target_rh, is_on, is_defrost
                FROM room_history
                WHERE room = ? AND timestamp >= ?
                ORDER BY timestamp ASC
                """,
                (room, cutoff),
            )
            rows = cur.fetchall()

        points: list[dict[str, Any]] = [
            {
                "timestamp": float(r["timestamp"]),
                "indoor_temp_c": r["indoor_temp_c"],
                "indoor_rh_percent": r["indoor_rh"],
                "outdoor_temp_c": r["outdoor_temp_c"],
                "dew_point_c": r["dew_point_c"],
                "safe_dew_point_c": r["safe_dew_point_c"],
                "target_rh": r["target_rh"],
                "is_on": None if r["is_on"] is None else bool(r["is_on"]),
                "is_defrost": None if r["is_defrost"] is None else bool(r["is_defrost"]),
            }
            for r in rows
        ]

        if max_points > 0 and len(points) > max_points:
            n = len(points)
            sampled: list[dict[str, Any]] = []
            for i in range(max_points):
                start = (i * n) // max_points
                end = max(start + 1, ((i + 1) * n) // max_points)
                if i == max_points - 1:
                    end = n
                bucket = points[start:end]
                rep = dict(bucket[-1])
                rep["is_on"] = _aggregate_bool_flag([p["is_on"] for p in bucket])
                rep["is_defrost"] = _aggregate_bool_flag([p["is_defrost"] for p in bucket])
                sampled.append(rep)
            return sampled

        return points

    def set_state(self, key: str, value: Any) -> None:
        """Persist a JSON-serializable runtime state value."""
        payload = json.dumps(value)
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO runtime_state (key, value)
                VALUES (?, ?)
                """,
                (key, payload),
            )
            self._conn.commit()

    def get_state(self, key: str) -> Any | None:
        """Retrieve a persisted runtime state value, or None if absent."""
        with self._lock:
            cur = self._conn.execute("SELECT value FROM runtime_state WHERE key = ?", (key,))
            row = cur.fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def delete_state(self, key: str) -> None:
        """Delete a persisted runtime state entry if present."""
        with self._lock:
            self._conn.execute("DELETE FROM runtime_state WHERE key = ?", (key,))
            self._conn.commit()

    def get_state_by_prefix(self, prefix: str) -> dict[str, Any]:
        """Return all persisted runtime state entries whose key starts with `prefix`."""
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        with self._lock:
            cur = self._conn.execute(
                "SELECT key, value FROM runtime_state WHERE key LIKE ? ESCAPE '\\'",
                (escaped,),
            )
            rows = cur.fetchall()
        return {str(r["key"]): json.loads(r["value"]) for r in rows}

    def get_all_rooms_history(
        self,
        hours: float = 24.0,
        max_points: int = 180,
        now_ts: float | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return historical time-series keyed by room name."""
        with self._lock:
            cur = self._conn.execute("SELECT DISTINCT room FROM room_history")
            rooms = [str(r["room"]) for r in cur.fetchall()]

        return {
            room: self.get_room_history(room, hours=hours, max_points=max_points, now_ts=now_ts)
            for room in rooms
        }

    def prune_old_records(
        self, retention_days: int | None = None, now_ts: float | None = None
    ) -> int:
        """Delete records older than `retention_days`."""
        days = retention_days if retention_days is not None else self.retention_days
        now = now_ts if now_ts is not None else time.time()
        cutoff = now - (days * 86400.0)

        with self._lock:
            cur1 = self._conn.execute("DELETE FROM room_history WHERE timestamp < ?", (cutoff,))
            cur2 = self._conn.execute("DELETE FROM device_events WHERE timestamp < ?", (cutoff,))
            self._conn.commit()
            return (cur1.rowcount or 0) + (cur2.rowcount or 0)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
