from __future__ import annotations

from app.database import connection, queue_firebase_sync
from app.services.common import ServiceError, new_id, timestamp_value


def create_decision(payload) -> dict:
    decision_id = new_id("DEC")
    timestamp = timestamp_value(payload.timestamp)
    with connection() as conn:
        if payload.train_id and not conn.execute(
            "SELECT 1 FROM train WHERE train_id=?", (payload.train_id,)
        ).fetchone():
            raise ServiceError(f"Train '{payload.train_id}' not found", 404)
        if payload.switch_id and not conn.execute(
            "SELECT 1 FROM track_switch WHERE switch_id=?", (payload.switch_id,)
        ).fetchone():
            raise ServiceError(f"Switch '{payload.switch_id}' not found", 404)
        for track_id in (payload.current_track, payload.selected_track):
            if track_id and not conn.execute("SELECT 1 FROM track WHERE track_id=?", (track_id,)).fetchone():
                raise ServiceError(f"Track '{track_id}' not found", 404)
        if payload.emergency_stop and payload.selected_track:
            raise ServiceError("selected_track must be omitted when emergency_stop is true", 400)
        conn.execute(
            """INSERT INTO switch_decision(decision_id,train_id,switch_id,current_track,selected_track,
               reason,confidence,emergency_stop,timestamp) VALUES (?,?,?,?,?,?,?,?,?)""",
            (decision_id, payload.train_id, payload.switch_id, payload.current_track, payload.selected_track,
             payload.reason, payload.confidence, int(payload.emergency_stop), timestamp),
        )
        row = dict(conn.execute("SELECT * FROM switch_decision WHERE decision_id=?", (decision_id,)).fetchone())
        row["emergency_stop"] = bool(row["emergency_stop"])
        current_track = payload.current_track if payload.emergency_stop else (payload.selected_track or payload.current_track)
        queue_firebase_sync(conn, "/switch_status", {"current_track": current_track, "last_decision": row})
    return row


def get_status() -> dict:
    with connection() as conn:
        row = conn.execute(
            "SELECT * FROM switch_decision ORDER BY timestamp DESC,rowid DESC LIMIT 1"
        ).fetchone()
    if not row:
        return {"current_track": None, "last_decision": None}
    decision = dict(row)
    decision["emergency_stop"] = bool(decision["emergency_stop"])
    current_track = decision["current_track"] if decision["emergency_stop"] else (
        decision["selected_track"] or decision["current_track"]
    )
    return {"current_track": current_track, "last_decision": decision}


def list_tracks() -> list[dict]:
    with connection() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM track ORDER BY track_id").fetchall()]

