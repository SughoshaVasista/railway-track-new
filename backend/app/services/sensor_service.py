from __future__ import annotations

from app.database import connection, queue_firebase_sync, utc_now
from app.services.common import ServiceError, timestamp_value


def register_sensor(payload) -> dict:
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM device WHERE device_id=?", (payload.device_id,)).fetchone():
            raise ServiceError(f"Device '{payload.device_id}' not found", 404)
        try:
            conn.execute(
                """INSERT INTO sensor(sensor_id,device_id,sensor_type,sampling_rate,status,created_at)
                   VALUES (?,?,?,?,'OFFLINE',?)""",
                (payload.sensor_id, payload.device_id, payload.sensor_type.value, payload.sampling_rate, utc_now()),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ServiceError(f"Sensor '{payload.sensor_id}' already exists", 409) from exc
            raise
        return dict(conn.execute("SELECT * FROM sensor WHERE sensor_id=?", (payload.sensor_id,)).fetchone())


def create_readings(payload) -> dict:
    received_at = utc_now()
    inserted = []
    with connection() as conn:
        device = conn.execute("SELECT 1 FROM device WHERE device_id=?", (payload.device_id,)).fetchone()
        if not device:
            raise ServiceError(f"Device '{payload.device_id}' not found", 404)
        sensor_ids = {reading.sensor_id for reading in payload.readings}
        sensors = conn.execute(
            f"SELECT sensor_id,sensor_type FROM sensor WHERE device_id=? AND sensor_id IN ({','.join('?' for _ in sensor_ids)})",
            [payload.device_id, *sorted(sensor_ids)],
        ).fetchall()
        sensor_map = {row["sensor_id"]: row["sensor_type"] for row in sensors}
        missing = sorted(sensor_ids - sensor_map.keys())
        if missing:
            raise ServiceError(f"Sensors not registered to device '{payload.device_id}': {', '.join(missing)}", 400)
        for reading in payload.readings:
            stamp = timestamp_value(reading.timestamp)
            cursor = conn.execute(
                "INSERT INTO sensor_reading(sensor_id,timestamp,value,axis) VALUES (?,?,?,?)",
                (reading.sensor_id, stamp, reading.value, reading.axis),
            )
            conn.execute("UPDATE sensor SET status='ONLINE' WHERE sensor_id=?", (reading.sensor_id,))
            inserted.append({
                "reading_id": cursor.lastrowid,
                "sensor_id": reading.sensor_id,
                "device_id": payload.device_id,
                "sensor_type": sensor_map[reading.sensor_id],
                "timestamp": stamp,
                "value": reading.value,
                "axis": reading.axis,
            })
        conn.execute(
            "UPDATE device SET status='ONLINE',last_seen=? WHERE device_id=?", (received_at, payload.device_id)
        )
        queue_firebase_sync(conn, f"/devices/{payload.device_id}", {"status": "ONLINE", "last_seen": received_at})
        latest_rows = conn.execute(
            """SELECT s.sensor_id,s.sensor_type,sr.timestamp,sr.value,sr.axis
               FROM sensor s JOIN sensor_reading sr ON sr.reading_id=(
                   SELECT r.reading_id FROM sensor_reading r WHERE r.sensor_id=s.sensor_id
                   ORDER BY r.timestamp DESC,r.reading_id DESC LIMIT 1)
               WHERE s.device_id=?""", (payload.device_id,)
        ).fetchall()
        latest = {
            row["sensor_id"]: {
                "sensor_type": row["sensor_type"], "timestamp": row["timestamp"],
                "value": row["value"], "axis": row["axis"],
            }
            for row in latest_rows
        }
        queue_firebase_sync(conn, f"/sensors_latest/{payload.device_id}", {"readings": latest, "updated_at": received_at})
    return {"inserted": len(inserted), "readings": inserted}


def latest_readings(device_id: str | None) -> list[dict]:
    with connection() as conn:
        if device_id and not conn.execute("SELECT 1 FROM device WHERE device_id=?", (device_id,)).fetchone():
            raise ServiceError(f"Device '{device_id}' not found", 404)
        params = (device_id,) if device_id else ()
        where = "WHERE s.device_id=?" if device_id else ""
        rows = conn.execute(
            f"""SELECT sr.reading_id,s.sensor_id,s.device_id,s.sensor_type,sr.timestamp,sr.value,sr.axis
                FROM sensor s JOIN sensor_reading sr ON sr.reading_id=(
                    SELECT r.reading_id FROM sensor_reading r WHERE r.sensor_id=s.sensor_id
                    ORDER BY r.timestamp DESC,r.reading_id DESC LIMIT 1)
                {where} ORDER BY s.device_id,s.sensor_id""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]

