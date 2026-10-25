from __future__ import annotations

from app.database import connection, queue_firebase_sync, utc_now
from app.services.common import ServiceError, timestamp_value
from app.services.dashboard_service import sync_summary


def create_device(payload) -> dict:
    now = utc_now()
    with connection() as conn:
        try:
            conn.execute(
                "INSERT INTO device(device_id,device_name,location,status,created_at) VALUES (?,?,?,'OFFLINE',?)",
                (payload.device_id, payload.device_name, payload.location, now),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ServiceError(f"Device '{payload.device_id}' already exists", 409) from exc
            raise
        result = dict(conn.execute("SELECT * FROM device WHERE device_id=?", (payload.device_id,)).fetchone())
        queue_firebase_sync(conn, f"/devices/{payload.device_id}", {"status": "OFFLINE", "last_seen": None})
        sync_summary(conn)
    return result


def list_devices() -> list[dict]:
    with connection() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM device ORDER BY device_id").fetchall()]


def get_device(device_id: str) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
    if not row:
        raise ServiceError(f"Device '{device_id}' not found", 404)
    return dict(row)


def heartbeat(device_id: str, timestamp=None, location: str | None = None) -> dict:
    seen = timestamp_value(timestamp)
    with connection() as conn:
        row = conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
        if not row:
            raise ServiceError(f"Device '{device_id}' not found", 404)
        conn.execute(
            "UPDATE device SET status='ONLINE',last_seen=?,location=COALESCE(?,location) WHERE device_id=?",
            (seen, location, device_id),
        )
        result = dict(conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone())
        queue_firebase_sync(conn, f"/devices/{device_id}", {"status": "ONLINE", "last_seen": seen})
        sync_summary(conn)
    return result


def get_health(device_id: str) -> dict:
    with connection() as conn:
        device = conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
        if not device:
            raise ServiceError(f"Device '{device_id}' not found", 404)
        sensors = conn.execute(
            "SELECT * FROM sensor WHERE device_id=? ORDER BY sensor_id", (device_id,)
        ).fetchall()
        latest = conn.execute(
            """SELECT sr.reading_id,s.sensor_id,s.device_id,s.sensor_type,sr.timestamp,sr.value,sr.axis
               FROM sensor s JOIN sensor_reading sr ON sr.reading_id=(
                   SELECT r.reading_id FROM sensor_reading r WHERE r.sensor_id=s.sensor_id
                   ORDER BY r.timestamp DESC,r.reading_id DESC LIMIT 1)
               WHERE s.device_id=? ORDER BY s.sensor_id""",
            (device_id,),
        ).fetchall()
    return {
        "device": dict(device),
        "sensors": [dict(row) for row in sensors],
        "latest_readings": [dict(row) for row in latest],
    }

