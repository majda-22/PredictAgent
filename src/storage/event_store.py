from pathlib import Path
import os
import sqlite3
from typing import Any


DEFAULT_DB_FILE = Path(os.getenv("MOTOR_EVENTS_DB", "motor_events.db"))
LEGACY_DB_FILE = Path("data/events/motor_events.db")


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temperature REAL,
    current REAL,
    voltage REAL,
    vibration REAL,
    score REAL,
    regime INTEGER,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    command TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class EventStore:
    def __init__(self, db_file: Path = DEFAULT_DB_FILE) -> None:
        self.db_file = db_file
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_file)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(SCHEMA)
            self._migrate_legacy_events(connection)
            connection.commit()

    def _migrate_legacy_events(self, connection: sqlite3.Connection) -> None:
        existing_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if existing_count > 0 or not LEGACY_DB_FILE.exists() or self.db_file == LEGACY_DB_FILE:
            return

        legacy = sqlite3.connect(LEGACY_DB_FILE)
        try:
            legacy.row_factory = sqlite3.Row
            legacy_tables = {
                row["name"]
                for row in legacy.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "prediction_events" not in legacy_tables:
                return
            rows = legacy.execute(
                """
                SELECT
                    timestamp,
                    temperature,
                    current,
                    voltage,
                    vibration,
                    score,
                    regime,
                    decision,
                    reason,
                    command,
                    created_at
                FROM prediction_events
                ORDER BY id
                """
            ).fetchall()
            connection.executemany(
                """
                INSERT INTO events (
                    timestamp,
                    temperature,
                    current,
                    voltage,
                    vibration,
                    score,
                    regime,
                    decision,
                    reason,
                    command,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [tuple(row) for row in rows],
            )
        finally:
            legacy.close()

    def record_prediction(
        self,
        *,
        timestamp: str,
        temperature: float,
        current: float,
        voltage: float,
        vibration: float,
        score: float | None,
        regime: int | None,
        decision: str,
        reason: str,
        command: str,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO events (
                    timestamp,
                    temperature,
                    current,
                    voltage,
                    vibration,
                    score,
                    regime,
                    decision,
                    reason,
                    command
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    temperature,
                    current,
                    voltage,
                    vibration,
                    score,
                    regime,
                    decision,
                    reason,
                    command,
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def latest_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT *
                FROM events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_motor_state(self) -> dict[str, Any] | None:
        events = self.latest_events(limit=1)
        return events[0] if events else None

    def recent_non_normal_events(self, hours: int = 1) -> list[dict[str, Any]]:
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT *
                FROM events
                WHERE decision != 'NORMAL'
                  AND created_at >= datetime('now', ?)
                ORDER BY id DESC
                """,
                (f"-{hours} hours",),
            ).fetchall()
        return [dict(row) for row in rows]

    def recent_events_for_trend(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(reversed(self.latest_events(limit=limit)))


_default_store = EventStore()


def save_event(sensor_data: dict[str, Any], result: dict[str, Any]) -> int:
    return _default_store.record_prediction(
        timestamp=str(sensor_data.get("timestamp", "")),
        temperature=float(sensor_data.get("temperature", 0.0)),
        current=float(sensor_data.get("current", 0.0)),
        voltage=float(sensor_data.get("voltage", 0.0)),
        vibration=float(
            sensor_data.get(
                "vibration",
                (
                    float(sensor_data.get("vibration_x", 0.0)) ** 2
                    + float(sensor_data.get("vibration_y", 0.0)) ** 2
                    + float(sensor_data.get("vibration_z", 0.0)) ** 2
                )
                ** 0.5,
            )
        ),
        score=result.get("score"),
        regime=result.get("regime"),
        decision=str(result.get("decision", "NORMAL")),
        reason=str(result.get("reason", "")),
        command=str(result.get("command", "NO_ACTION")),
    )
