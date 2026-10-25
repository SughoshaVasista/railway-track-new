from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query

from app.database import connection, queue_firebase_sync, utc_now
from app.services.alert_service import ALERT_SELECT, _alert
from app.services.dashboard_service import sync_summary
from app.services import task_service
from app.services.common import ServiceError

router = APIRouter(tags=["frontend compatibility"])


def _legacy_alert(row):
    item = dict(row)
    status = item.pop("lifecycle_status", None)
    item["id"] = item["alert_id"]
    item["defect"] = item["defect_type"]
    item["type"] = item["defect_type"]
    item["track"] = item.get("device_location") or "NO DATA"
    item["status"] = status or {"ACTIVE": "DETECTED", "IN_PROGRESS": "UNDER_REPAIR"}.get(item["status"], item["status"])
    item["gps"] = {"lat": item.get("latitude"), "lng": item.get("longitude")}
    item["image"] = item.get("image_url")
    return item


ALERT_QUERY = """SELECT a.alert_id,a.priority,a.status,a.created_at,a.resolved_at,
 d.defect_type,d.confidence,d.severity,d.latitude,d.longitude,d.chainage,d.timestamp,d.image_url,
 device.device_name,device.location AS device_location,l.status AS lifecycle_status
 FROM alert a JOIN defect d ON d.defect_id=a.defect_id
 JOIN device ON device.device_id=d.device_id
 LEFT JOIN alert_lifecycle l ON l.alert_id=a.alert_id"""


@router.post("/api/auth/login")
def demo_login(payload: dict):
    # The frontend's demo accounts are intentionally limited to development mode.
    from app.config import get_settings
    settings = get_settings()
    username, password = payload.get("username"), payload.get("password")
    if settings.app_env == "production":
        raise ServiceError("Configure an authentication provider for production login", 503)
    if (username, password) not in {("admin", "admin"), ("worker", "worker")}:
        raise ServiceError("Invalid credentials", 401)
    role = username
    result = {"token": f"dev-{username}-token", "role": role, "name": "Admin User" if role == "admin" else "Maintenance Worker"}
    if role == "worker":
        with connection() as conn:
            worker = conn.execute("SELECT user_id FROM app_user WHERE role='WORKER' AND status='ACTIVE' ORDER BY user_id LIMIT 1").fetchone()
        if not worker:
            raise ServiceError("No active worker account is available", 403)
        result["worker_id"] = worker["user_id"]
    return result


@router.get("/api/workers")
def workers():
    with connection() as conn:
        rows = conn.execute("SELECT user_id,name,status,role,email,phone FROM app_user WHERE role='WORKER' ORDER BY name").fetchall()
    return {"items": [{"id": r["user_id"], "worker_id": r["user_id"], "name": r["name"], "status": r["status"], "role": "worker", "email": r["email"], "phone": r["phone"]} for r in rows]}


@router.get("/api/tracks")
def tracks():
    with connection() as conn:
        rows = conn.execute("SELECT * FROM track ORDER BY track_id").fetchall()
    return {"items": [{**dict(r), "id": r["track_id"], "name": r["track_name"]} for r in rows]}


@router.get("/api/trains")
def trains():
    with connection() as conn:
        rows = conn.execute("SELECT * FROM train ORDER BY train_id").fetchall()
    return {"items": [{**dict(r), "id": r["train_id"], "name": r["train_name"]} for r in rows]}


@router.get("/api/simulation/state")
def simulation_state():
    with connection() as conn:
        mode = conn.execute("SELECT * FROM simulation_state WHERE state_id=1").fetchone()
        row = conn.execute("SELECT * FROM train ORDER BY train_id LIMIT 1").fetchone()
    if not row:
        return {"status": "DISCONNECTED", "mode": mode["mode"] if mode else "live", "scenario": mode["scenario"] if mode else None, "position": None}
    return {"status": row["status"] or "CONNECTED", "mode": mode["mode"] if mode else "live", "scenario": mode["scenario"] if mode else None, "position": row["position"], "train_id": row["train_id"]}


@router.post("/api/simulation/mode")
def simulation_mode(payload: dict):
    mode = payload.get("mode")
    if mode not in {"live", "simulation"}:
        raise ServiceError("mode must be 'live' or 'simulation'", 422)
    updated = utc_now()
    with connection() as conn:
        conn.execute("INSERT INTO simulation_state(state_id,mode,scenario,updated_at) VALUES (1,?,?,?) ON CONFLICT(state_id) DO UPDATE SET mode=excluded.mode,scenario=excluded.scenario,updated_at=excluded.updated_at", (mode, payload.get("scenario"), updated))
    return {"mode": mode, "scenario": payload.get("scenario"), "updated_at": updated}


@router.get("/api/dashboard/event-log")
def event_log(limit: int = Query(default=50, ge=1, le=200)):
    with connection() as conn:
        alerts = conn.execute("SELECT alert_id AS id,'ALERT' AS type,defect_type AS description,timestamp FROM defect ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        tasks = conn.execute("SELECT task_id AS id,'TASK' AS type,status AS description,COALESCE(completed_at,started_at,assigned_at) AS timestamp FROM maintenance_task ORDER BY assigned_at DESC LIMIT ?", (limit,)).fetchall()
        decisions = conn.execute("SELECT decision_id AS id,'SWITCH' AS type,reason AS description,timestamp FROM switch_decision ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    rows = sorted([dict(r) for group in (alerts, tasks, decisions) for r in group], key=lambda r: r["timestamp"] or "", reverse=True)[:limit]
    return {"items": rows, "generated_at": utc_now()}


@router.get("/api/alerts/{alert_id}/history")
def alert_history(alert_id: str):
    with connection() as conn:
        if not conn.execute("SELECT 1 FROM alert WHERE alert_id=?", (alert_id,)).fetchone():
            raise ServiceError(f"Alert '{alert_id}' not found", 404)
        rows = conn.execute("SELECT event_id AS id,action,details_json,timestamp FROM alert_event WHERE alert_id=? ORDER BY event_id", (alert_id,)).fetchall()
    return [{**dict(r), "details": json.loads(r["details_json"]) if r["details_json"] else None} for r in rows]


@router.post("/api/alerts/{alert_id}/{action}")
def alert_action(alert_id: str, action: str, payload: dict | None = None):
    allowed_actions = {"acknowledge", "resolve", "false-positive", "assign", "priority"}
    if action not in allowed_actions:
        raise ServiceError("Unsupported alert action", 404)
    body = payload or {}
    now = utc_now()
    with connection() as conn:
        row = conn.execute(f"{ALERT_QUERY} WHERE a.alert_id=?", (alert_id,)).fetchone()
        if not row:
            raise ServiceError(f"Alert '{alert_id}' not found", 404)
        current = _legacy_alert(row)
        target = {"acknowledge": "ACKNOWLEDGED", "resolve": "RESOLVED", "false-positive": "FALSE_POSITIVE", "assign": "ASSIGNED"}.get(action)
        transitions = {
            "acknowledge": {"DETECTED", "VERIFIED", "REOPENED"},
            "assign": {"ACKNOWLEDGED"},
            "resolve": {"UNDER_REPAIR"},
            "false-positive": {"DETECTED", "VERIFIED", "ACKNOWLEDGED", "ASSIGNED", "UNDER_REPAIR", "REOPENED"},
        }
        if action in transitions and current["status"] not in transitions[action]:
            raise ServiceError(f"Cannot {action} an alert in {current['status']} status", 409)
        if action == "assign":
            worker_id = body.get("worker_id") or body.get("assigned_worker_id")
            worker = conn.execute("SELECT 1 FROM app_user WHERE user_id=? AND role='WORKER' AND status='ACTIVE'", (worker_id,)).fetchone()
            if not worker:
                raise ServiceError("An active worker_id is required", 400)
            task = conn.execute("SELECT task_id FROM maintenance_task WHERE alert_id=? ORDER BY assigned_at DESC LIMIT 1", (alert_id,)).fetchone()
            if task:
                task_id = task["task_id"]
                conn.execute("UPDATE maintenance_task SET assigned_worker_id=? WHERE task_id=?", (worker_id, task_id))
            else:
                task_id = f"TASK_{alert_id}"
                conn.execute("INSERT INTO maintenance_task(task_id,alert_id,assigned_worker_id,priority,status,assigned_at) VALUES (?,?,?,?,'ASSIGNED',?)", (task_id, alert_id, worker_id, row["priority"], now))
            task_row = conn.execute("SELECT * FROM maintenance_task WHERE task_id=?", (task_id,)).fetchone()
            queue_firebase_sync(conn, f"/tasks/{task_id}", task_service._task_view(conn, task_row))
        elif action == "priority":
            severity = body.get("severity")
            mapping = {"S1": "LOW", "S2": "MEDIUM", "S3": "CRITICAL"}
            if severity not in mapping:
                raise ServiceError("severity must be S1, S2, or S3", 422)
            conn.execute("UPDATE alert SET priority=? WHERE alert_id=?", (mapping[severity], alert_id))
            conn.execute("UPDATE defect SET severity=? WHERE defect_id=(SELECT defect_id FROM alert WHERE alert_id=?)", (severity, alert_id))
            target = current["status"]
        if target:
            conn.execute("INSERT INTO alert_lifecycle(alert_id,status,updated_at) VALUES (?,?,?) ON CONFLICT(alert_id) DO UPDATE SET status=excluded.status,updated_at=excluded.updated_at", (alert_id, target, now))
            if target in {"RESOLVED", "FALSE_POSITIVE"}:
                conn.execute("UPDATE alert SET status='RESOLVED',resolved_at=? WHERE alert_id=?", (now, alert_id))
            elif target in {"ACKNOWLEDGED", "ASSIGNED"}:
                conn.execute("UPDATE alert SET status='ASSIGNED' WHERE alert_id=?", (alert_id,))
        if action == "priority":
            conn.execute("UPDATE alert_lifecycle SET updated_at=? WHERE alert_id=?", (now, alert_id))
        conn.execute("INSERT INTO alert_event(alert_id,action,details_json,timestamp) VALUES (?,?,?,?)", (alert_id, action, json.dumps(body), now))
        sync_row = conn.execute(f"{ALERT_SELECT} WHERE a.alert_id=?", (alert_id,)).fetchone()
        queue_firebase_sync(conn, f"/alerts/{alert_id}", _alert(sync_row))
        sync_summary(conn)
        updated = conn.execute(f"{ALERT_QUERY} WHERE a.alert_id=?", (alert_id,)).fetchone()
    return _legacy_alert(updated)


@router.get("/api/devices/{device_id}/sensors")
def device_sensors(device_id: str, history: bool = False, window: str = "24h"):
    with connection() as conn:
        device = conn.execute("SELECT 1 FROM device WHERE device_id=?", (device_id,)).fetchone()
        if not device:
            raise ServiceError(f"Device '{device_id}' not found", 404)
        sensors = conn.execute("SELECT * FROM sensor WHERE device_id=? ORDER BY sensor_id", (device_id,)).fetchall()
        result = []
        for sensor in sensors:
            latest = conn.execute("SELECT value,axis,timestamp FROM sensor_reading WHERE sensor_id=? ORDER BY timestamp DESC,reading_id DESC LIMIT 1", (sensor["sensor_id"],)).fetchone()
            item = {**dict(sensor), "id": sensor["sensor_id"], "name": sensor["sensor_type"].title(), "type": sensor["sensor_type"], "value": latest["value"] if latest else None, "axis": latest["axis"] if latest else None, "timestamp": latest["timestamp"] if latest else None}
            if history:
                hours = {"1h": 1, "24h": 24, "7d": 168}.get(window, 24)
                since = (datetime.now(UTC) - timedelta(hours=hours)).isoformat().replace("+00:00", "Z")
                readings = conn.execute("SELECT value,axis,timestamp FROM sensor_reading WHERE sensor_id=? AND timestamp>=? ORDER BY timestamp", (sensor["sensor_id"], since)).fetchall()
                item["history"] = [dict(r) for r in readings]
            result.append(item)
    return {"items": result}


@router.get("/api/devices/{device_id}/diagnostics")
def device_diagnostics(device_id: str):
    with connection() as conn:
        device = conn.execute("SELECT * FROM device WHERE device_id=?", (device_id,)).fetchone()
        if not device:
            raise ServiceError(f"Device '{device_id}' not found", 404)
        return {"device_id": device_id, "status": "OK" if device["status"] == "ONLINE" else "OFFLINE", "pi_status": device["status"], "network_status": "UNKNOWN", "uptime": None, "checks": [], "updated_at": device["last_seen"]}
