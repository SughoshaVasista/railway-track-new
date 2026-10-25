from __future__ import annotations

import json

from app.database import connection, queue_firebase_sync, utc_now
from app.services.common import ServiceError, new_id, priority_for_severity, row_dict, timestamp_value
from app.services.dashboard_service import sync_summary


ALERT_SELECT = """SELECT a.alert_id, a.defect_id, a.priority, a.status, a.created_at, a.resolved_at,
    d.device_id, d.sensor_id, d.defect_type, d.confidence, d.severity, d.latitude, d.longitude,
    d.chainage, d.timestamp, d.image_url, d.bbox_json,
    device.device_name AS device_name, device.location AS device_location, sensor.sensor_type AS sensor_type,
    lifecycle.status AS lifecycle_status
    FROM alert a JOIN defect d ON d.defect_id = a.defect_id
    JOIN device ON device.device_id = d.device_id LEFT JOIN sensor ON sensor.sensor_id = d.sensor_id
    LEFT JOIN alert_lifecycle lifecycle ON lifecycle.alert_id=a.alert_id"""


def _alert(row) -> dict:
    data = dict(row)
    raw_bbox = data.pop("bbox_json", None)
    data["bbox"] = json.loads(raw_bbox) if raw_bbox else None
    lifecycle_status = data.pop("lifecycle_status", None)
    data["id"] = data["alert_id"]
    data["defect"] = data["defect_type"]
    data["type"] = data["defect_type"]
    data["track"] = data.get("device_location") or "NO DATA"
    data["status"] = lifecycle_status or {"ACTIVE": "DETECTED", "IN_PROGRESS": "UNDER_REPAIR"}.get(data["status"], data["status"])
    data["gps"] = {"lat": data.get("latitude"), "lng": data.get("longitude")}
    data["image"] = data.get("image_url")
    return data


def create_alert(payload) -> dict:
    alert_id, defect_id = new_id("ALT"), new_id("DEF")
    now = utc_now()
    timestamp = timestamp_value(payload.timestamp)
    priority = payload.priority.value if payload.priority else priority_for_severity(payload.severity.value)
    bbox = payload.bbox.model_dump(mode="json") if payload.bbox else None
    with connection() as conn:
        device = conn.execute("SELECT 1 FROM device WHERE device_id=?", (payload.device_id,)).fetchone()
        if not device:
            raise ServiceError(f"Device '{payload.device_id}' not found", 404)
        if payload.sensor_id:
            sensor = conn.execute(
                "SELECT 1 FROM sensor WHERE sensor_id=? AND device_id=?",
                (payload.sensor_id, payload.device_id),
            ).fetchone()
            if not sensor:
                raise ServiceError("Sensor does not belong to the specified device", 400)
        conn.execute(
            """INSERT INTO defect(defect_id,device_id,sensor_id,defect_type,confidence,severity,
               latitude,longitude,chainage,timestamp,image_url,bbox_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (defect_id, payload.device_id, payload.sensor_id, payload.defect_type.value,
             payload.confidence, payload.severity.value, payload.latitude, payload.longitude,
             payload.chainage, timestamp, payload.image_url,
             json.dumps(bbox, separators=(",", ":")) if bbox else None),
        )
        conn.execute(
            "INSERT INTO alert(alert_id,defect_id,priority,status,created_at) VALUES (?,?,?,'ACTIVE',?)",
            (alert_id, defect_id, priority, now),
        )
        record = _alert(conn.execute(f"{ALERT_SELECT} WHERE a.alert_id=?", (alert_id,)).fetchone())
        queue_firebase_sync(conn, f"/alerts/{alert_id}", record)
        sync_summary(conn)
    return record


def list_alerts(status: str | None, severity: str | None, limit: int, offset: int) -> dict:
    clauses, params = [], []
    if status:
        clauses.append("COALESCE(lifecycle.status, CASE a.status WHEN 'ACTIVE' THEN 'DETECTED' WHEN 'IN_PROGRESS' THEN 'UNDER_REPAIR' ELSE a.status END)=?")
        params.append(status)
    if severity:
        clauses.append("d.severity=?")
        params.append(severity)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connection() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM alert a JOIN defect d ON d.defect_id=a.defect_id LEFT JOIN alert_lifecycle lifecycle ON lifecycle.alert_id=a.alert_id{where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"{ALERT_SELECT}{where} ORDER BY a.created_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return {"items": [_alert(row) for row in rows], "total": total, "limit": limit, "offset": offset}


def get_alert(alert_id: str) -> dict:
    with connection() as conn:
        row = conn.execute(f"{ALERT_SELECT} WHERE a.alert_id=?", (alert_id,)).fetchone()
    if not row:
        raise ServiceError(f"Alert '{alert_id}' not found", 404)
    return _alert(row)


def update_status(alert_id: str, status: str) -> dict:
    status_map = {
        "DETECTED": "ACTIVE", "VERIFIED": "ACTIVE", "REOPENED": "ACTIVE",
        "ACKNOWLEDGED": "ASSIGNED", "ASSIGNED": "ASSIGNED",
        "UNDER_REPAIR": "IN_PROGRESS", "IN_PROGRESS": "IN_PROGRESS",
        "RESOLVED": "RESOLVED", "FALSE_POSITIVE": "RESOLVED",
        "ACTIVE": "ACTIVE",
    }
    stored_status = status_map.get(status)
    if not stored_status:
        raise ServiceError(f"Unsupported alert status '{status}'", 422)
    now = utc_now()
    with connection() as conn:
        row = conn.execute("SELECT alert_id FROM alert WHERE alert_id=?", (alert_id,)).fetchone()
        if not row:
            raise ServiceError(f"Alert '{alert_id}' not found", 404)
        resolved_at = now if stored_status == "RESOLVED" else None
        conn.execute("UPDATE alert SET status=?,resolved_at=? WHERE alert_id=?", (stored_status, resolved_at, alert_id))
        if status not in {"ACTIVE", "ASSIGNED", "IN_PROGRESS", "RESOLVED"}:
            conn.execute("INSERT INTO alert_lifecycle(alert_id,status,updated_at) VALUES (?,?,?) ON CONFLICT(alert_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at", (alert_id, status, now))
            conn.execute("INSERT INTO alert_event(alert_id,action,details_json,timestamp) VALUES (?,?,NULL,?)", (alert_id, status, now))
        else:
            conn.execute("DELETE FROM alert_lifecycle WHERE alert_id=?", (alert_id,))
        record = _alert(conn.execute(f"{ALERT_SELECT} WHERE a.alert_id=?", (alert_id,)).fetchone())
        queue_firebase_sync(conn, f"/alerts/{alert_id}", record)
        sync_summary(conn)
    return record

