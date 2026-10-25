from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS device (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    location TEXT,
    status TEXT NOT NULL DEFAULT 'OFFLINE' CHECK(status IN ('ONLINE','OFFLINE')),
    last_seen TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sensor (
    sensor_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES device(device_id) ON DELETE CASCADE,
    sensor_type TEXT NOT NULL CHECK(sensor_type IN ('CAMERA','ULTRASONIC','ACCELEROMETER','TEMPERATURE','GPS')),
    sampling_rate REAL CHECK(sampling_rate IS NULL OR sampling_rate > 0),
    status TEXT NOT NULL DEFAULT 'OFFLINE' CHECK(status IN ('ONLINE','DELAYED','OFFLINE')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sensor_device ON sensor(device_id);
CREATE TABLE IF NOT EXISTS sensor_reading (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id TEXT NOT NULL REFERENCES sensor(sensor_id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    value REAL NOT NULL,
    axis TEXT
);
CREATE INDEX IF NOT EXISTS idx_reading_sensor_time ON sensor_reading(sensor_id, timestamp DESC);
CREATE TABLE IF NOT EXISTS defect (
    defect_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL REFERENCES device(device_id),
    sensor_id TEXT REFERENCES sensor(sensor_id),
    defect_type TEXT NOT NULL CHECK(defect_type IN ('CRACK','RUST','JOINT_GAP','MISSING_FASTENER','RAILWAY_GAP')),
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    severity TEXT NOT NULL CHECK(severity IN ('S1','S2','S3')),
    latitude REAL,
    longitude REAL,
    chainage TEXT,
    timestamp TEXT NOT NULL,
    image_url TEXT,
    bbox_json TEXT,
    CHECK(latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
    CHECK(longitude IS NULL OR (longitude >= -180 AND longitude <= 180))
);
CREATE INDEX IF NOT EXISTS idx_defect_device_time ON defect(device_id, timestamp DESC);
CREATE TABLE IF NOT EXISTS alert (
    alert_id TEXT PRIMARY KEY,
    defect_id TEXT NOT NULL UNIQUE REFERENCES defect(defect_id),
    priority TEXT NOT NULL CHECK(priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','ASSIGNED','IN_PROGRESS','RESOLVED')),
    created_at TEXT NOT NULL,
    resolved_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_status_time ON alert(status, created_at DESC);
CREATE TABLE IF NOT EXISTS app_user (
    user_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    role TEXT NOT NULL CHECK(role IN ('ADMIN','WORKER')),
    phone TEXT,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','INACTIVE'))
);
CREATE TABLE IF NOT EXISTS maintenance_task (
    task_id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL REFERENCES alert(alert_id),
    assigned_worker_id TEXT REFERENCES app_user(user_id),
    priority TEXT NOT NULL CHECK(priority IN ('LOW','MEDIUM','HIGH','CRITICAL')),
    status TEXT NOT NULL DEFAULT 'ASSIGNED' CHECK(status IN ('ASSIGNED','ACCEPTED','IN_PROGRESS','COMPLETED')),
    assigned_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    completion_image TEXT,
    remarks TEXT
);
CREATE INDEX IF NOT EXISTS idx_task_status_worker ON maintenance_task(status, assigned_worker_id);
CREATE TABLE IF NOT EXISTS train (
    train_id TEXT PRIMARY KEY,
    train_name TEXT,
    current_track TEXT REFERENCES track(track_id),
    speed REAL,
    position REAL,
    destination TEXT,
    status TEXT
);
CREATE TABLE IF NOT EXISTS track (
    track_id TEXT PRIMARY KEY,
    track_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('CLEAR','BLOCKED','OCCUPIED')),
    occupancy INTEGER NOT NULL DEFAULT 0 CHECK(occupancy IN (0,1)),
    max_speed REAL
);
CREATE TABLE IF NOT EXISTS track_switch (
    switch_id TEXT PRIMARY KEY,
    from_track TEXT REFERENCES track(track_id),
    to_track TEXT REFERENCES track(track_id),
    current_state TEXT,
    status TEXT NOT NULL DEFAULT 'AVAILABLE' CHECK(status IN ('AVAILABLE','UNAVAILABLE'))
);
CREATE TABLE IF NOT EXISTS switch_decision (
    decision_id TEXT PRIMARY KEY,
    train_id TEXT REFERENCES train(train_id),
    switch_id TEXT REFERENCES track_switch(switch_id),
    current_track TEXT,
    selected_track TEXT,
    reason TEXT NOT NULL,
    confidence REAL CHECK(confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    emergency_stop INTEGER NOT NULL DEFAULT 0 CHECK(emergency_stop IN (0,1)),
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_switch_decision_time ON switch_decision(timestamp DESC);
CREATE TABLE IF NOT EXISTS sync_outbox (
    outbox_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_path TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS idx_sync_outbox_due ON sync_outbox(next_attempt_at, outbox_id);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    db_path = get_settings().database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 10000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def initialize_database() -> None:
    with connection() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)


def queue_firebase_sync(conn: sqlite3.Connection, path: str, payload: dict[str, Any]) -> None:
    settings = get_settings()
    if not settings.firebase_enabled:
        return
    now = utc_now()
    conn.execute(
        "INSERT INTO sync_outbox(target_path,payload_json,created_at,next_attempt_at) VALUES (?,?,?,?)",
        (path, json.dumps(payload, separators=(",", ":"), allow_nan=False), now, now),
    )


def check_database() -> bool:
    with connection() as conn:
        return conn.execute("SELECT 1").fetchone()[0] == 1

