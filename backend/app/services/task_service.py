from __future__ import annotations

from app.database import connection, queue_firebase_sync, utc_now
from app.services.alert_service import ALERT_SELECT, _alert
from app.services.common import ServiceError, new_id
from app.services.dashboard_service import sync_summary


def _get_task(conn, task_id: str):
    return conn.execute("SELECT * FROM maintenance_task WHERE task_id=?", (task_id,)).fetchone()


def _task_view(conn, row) -> dict:
    result = dict(row)
    result["id"] = result["task_id"]
    result["worker_id"] = result.get("assigned_worker_id")
    details = conn.execute(
        """SELECT d.defect_type,d.chainage,d.image_url FROM alert a
           JOIN defect d ON d.defect_id=a.defect_id WHERE a.alert_id=?""",
        (result["alert_id"],),
    ).fetchone()
    if details:
        result.update({"defect": details["defect_type"], "chainage": details["chainage"], "image_url": details["image_url"], "before_image_url": details["image_url"], "after_image_url": result.get("completion_image")})
    return result


def _check_worker(conn, worker_id: str | None) -> None:
    if worker_id is None:
        return
    worker = conn.execute(
        "SELECT 1 FROM app_user WHERE user_id=? AND role='WORKER' AND status='ACTIVE'", (worker_id,)
    ).fetchone()
    if not worker:
        raise ServiceError(f"Active worker '{worker_id}' not found", 404)


def _sync_alert(conn, alert_id: str) -> None:
    alert = conn.execute(f"{ALERT_SELECT} WHERE a.alert_id=?", (alert_id,)).fetchone()
    if alert:
        queue_firebase_sync(conn, f"/alerts/{alert_id}", _alert(alert))


def list_tasks(worker_id: str | None, status: str | None, limit: int, offset: int) -> dict:
    clauses, params = [], []
    if worker_id:
        clauses.append("assigned_worker_id=?")
        params.append(worker_id)
    if status:
        clauses.append("status=?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM maintenance_task{where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM maintenance_task{where} ORDER BY assigned_at DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    with connection() as conn:
        items = [_task_view(conn, row) for row in rows]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def get_task(task_id: str) -> dict:
    with connection() as conn:
        row = _get_task(conn, task_id)
    if not row:
        raise ServiceError(f"Task '{task_id}' not found", 404)
    with connection() as conn:
        return _task_view(conn, row)


def create_task(payload) -> dict:
    task_id, now = new_id("TASK"), utc_now()
    with connection() as conn:
        alert = conn.execute("SELECT priority,status FROM alert WHERE alert_id=?", (payload.alert_id,)).fetchone()
        if not alert:
            raise ServiceError(f"Alert '{payload.alert_id}' not found", 404)
        if alert["status"] == "RESOLVED":
            raise ServiceError("Cannot create a maintenance task for a resolved alert", 409)
        _check_worker(conn, payload.assigned_worker_id)
        priority = payload.priority.value if payload.priority else alert["priority"]
        conn.execute(
            """INSERT INTO maintenance_task(task_id,alert_id,assigned_worker_id,priority,status,assigned_at,remarks)
               VALUES (?,?,?,?,'ASSIGNED',?,?)""",
            (task_id, payload.alert_id, payload.assigned_worker_id, priority, now, payload.remarks),
        )
        conn.execute("UPDATE alert SET status='ASSIGNED' WHERE alert_id=? AND status='ACTIVE'", (payload.alert_id,))
        conn.execute("INSERT INTO alert_lifecycle(alert_id,status,updated_at) VALUES (?, 'ASSIGNED', ?) ON CONFLICT(alert_id) DO UPDATE SET status='ASSIGNED',updated_at=excluded.updated_at", (payload.alert_id, now))
        conn.execute("INSERT INTO alert_event(alert_id,action,details_json,timestamp) VALUES (?, 'ASSIGNED', ?, ?)", (payload.alert_id, '{"source":"task_assignment"}', now))
        record = _task_view(conn, _get_task(conn, task_id))
        queue_firebase_sync(conn, f"/tasks/{task_id}", record)
        _sync_alert(conn, payload.alert_id)
        sync_summary(conn)
    return record


def update_task(task_id: str, payload) -> dict:
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if not changes:
        raise ServiceError("At least one task field must be provided", 400)
    with connection() as conn:
        current = _get_task(conn, task_id)
        if not current:
            raise ServiceError(f"Task '{task_id}' not found", 404)
        if current["status"] == "COMPLETED":
            raise ServiceError("Completed tasks are immutable", 409)
        if "assigned_worker_id" in changes:
            _check_worker(conn, changes["assigned_worker_id"])
        fields = [key for key in ("assigned_worker_id", "priority", "completion_image", "remarks") if key in changes]
        values = [changes[key] for key in fields]
        if fields:
            conn.execute(
                f"UPDATE maintenance_task SET {','.join(f'{field}=?' for field in fields)} WHERE task_id=?",
                [*values, task_id],
            )
        record = _task_view(conn, _get_task(conn, task_id))
        queue_firebase_sync(conn, f"/tasks/{task_id}", record)
    return record


def update_status(task_id: str, payload) -> dict:
    allowed = {
        "ASSIGNED": {"ACCEPTED", "IN_PROGRESS"},
        "ACCEPTED": {"IN_PROGRESS"},
        "IN_PROGRESS": {"COMPLETED"},
        "COMPLETED": set(),
    }
    now = utc_now()
    with connection() as conn:
        current = _get_task(conn, task_id)
        if not current:
            raise ServiceError(f"Task '{task_id}' not found", 404)
        if payload.status.value not in allowed[current["status"]]:
            raise ServiceError(
                f"Invalid task transition: {current['status']} -> {payload.status.value}", 409
            )
        started = now if payload.status.value == "IN_PROGRESS" else current["started_at"]
        completed = now if payload.status.value == "COMPLETED" else current["completed_at"]
        remarks = payload.remarks if payload.remarks is not None else current["remarks"]
        completion_image = payload.completion_image or current["completion_image"]
        conn.execute(
            """UPDATE maintenance_task SET status=?,started_at=?,completed_at=?,remarks=?,completion_image=?
               WHERE task_id=?""",
            (payload.status.value, started, completed, remarks, completion_image, task_id),
        )
        record = _task_view(conn, _get_task(conn, task_id))
        queue_firebase_sync(conn, f"/tasks/{task_id}", record)
        if payload.status.value == "IN_PROGRESS":
            conn.execute(
                "UPDATE alert SET status='IN_PROGRESS' WHERE alert_id=? AND status!='RESOLVED'",
                (record["alert_id"],),
            )
            conn.execute("INSERT INTO alert_lifecycle(alert_id,status,updated_at) VALUES (?, 'UNDER_REPAIR', ?) ON CONFLICT(alert_id) DO UPDATE SET status='UNDER_REPAIR',updated_at=excluded.updated_at", (record["alert_id"], now))
            conn.execute("INSERT INTO alert_event(alert_id,action,details_json,timestamp) VALUES (?, 'UNDER_REPAIR', ?, ?)", (record["alert_id"], '{"source":"task_status"}', now))
            _sync_alert(conn, record["alert_id"])
        if payload.status.value == "COMPLETED":
            remaining = conn.execute(
                "SELECT COUNT(*) FROM maintenance_task WHERE alert_id=? AND status!='COMPLETED'",
                (record["alert_id"],),
            ).fetchone()[0]
            if remaining == 0:
                conn.execute(
                    "UPDATE alert SET status='RESOLVED',resolved_at=? WHERE alert_id=?",
                    (now, record["alert_id"]),
                )
                conn.execute("INSERT INTO alert_lifecycle(alert_id,status,updated_at) VALUES (?, 'RESOLVED', ?) ON CONFLICT(alert_id) DO UPDATE SET status='RESOLVED',updated_at=excluded.updated_at", (record["alert_id"], now))
                conn.execute("INSERT INTO alert_event(alert_id,action,details_json,timestamp) VALUES (?, 'RESOLVED', ?, ?)", (record["alert_id"], '{"source":"task_completion"}', now))
                _sync_alert(conn, record["alert_id"])
        sync_summary(conn)
    return record

