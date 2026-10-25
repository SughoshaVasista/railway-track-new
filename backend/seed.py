from __future__ import annotations

from app.database import connection, initialize_database, queue_firebase_sync, utc_now
from app.services.alert_service import ALERT_SELECT, _alert
from app.services.dashboard_service import compute_summary


def seed() -> None:
    initialize_database()
    now = utc_now()
    devices = [
        ("AMRIN_01", "Inspection trolley 01", "Bengaluru north", "ONLINE", now),
        ("AMRIN_02", "Inspection trolley 02", "Bengaluru east", "ONLINE", now),
        ("AMRIN_03", "Inspection trolley 03", "Bengaluru south", "OFFLINE", None),
    ]
    sensors = [
        ("CAM_01", "AMRIN_01", "CAMERA", 2.0),
        ("US_01", "AMRIN_01", "ULTRASONIC", 10.0),
        ("ACC_01", "AMRIN_02", "ACCELEROMETER", 50.0),
        ("TEMP_01", "AMRIN_02", "TEMPERATURE", 1.0),
        ("GPS_01", "AMRIN_03", "GPS", 1.0),
    ]
    users = [
        ("USR_ADMIN", "AMRIN Administrator", "admin@amrin.local", "ADMIN", "+91-9000000001", "ACTIVE"),
        ("USR_WORKER", "Track Worker", "worker@amrin.local", "WORKER", "+91-9000000002", "ACTIVE"),
    ]
    tracks = [
        ("TRACK_A", "Track A", "CLEAR", 0, 80.0),
        ("TRACK_B", "Track B", "CLEAR", 0, 80.0),
        ("TRACK_C", "Track C", "OCCUPIED", 1, 40.0),
    ]
    switches = [
        ("SW_01", "TRACK_A", "TRACK_B", "A_TO_B", "AVAILABLE"),
        ("SW_02", "TRACK_B", "TRACK_C", "B_TO_C", "AVAILABLE"),
    ]
    trains = [
        ("TRAIN_01", "Regional 101", "TRACK_A", 42.0, 1250.0, "Bengaluru City", "RUNNING"),
        ("TRAIN_02", "Freight 208", "TRACK_C", 0.0, 460.0, "Yeshwanthpur", "HOLD"),
    ]

    examples = [
        ("CRACK", "S3", "ACTIVE", "AMRIN_01", .97, 12.9716, 77.5946, "KM 12/4"),
        ("RAILWAY_GAP", "S2", "ASSIGNED", "AMRIN_01", .91, 12.9720, 77.5950, "KM 12/5"),
        ("RUST", "S1", "IN_PROGRESS", "AMRIN_02", .86, 12.9730, 77.5961, "KM 13/1"),
        ("MISSING_FASTENER", "S2", "ACTIVE", "AMRIN_02", .89, 12.9742, 77.5974, "KM 13/2"),
        ("JOINT_GAP", "S3", "RESOLVED", "AMRIN_01", .95, 12.9751, 77.5981, "KM 13/3"),
        ("CRACK", "S2", "RESOLVED", "AMRIN_02", .90, 12.9762, 77.5993, "KM 13/4"),
        ("RAILWAY_GAP", "S1", "ACTIVE", "AMRIN_03", .84, 12.9771, 77.6001, "KM 14/1"),
        ("RUST", "S3", "ASSIGNED", "AMRIN_01", .93, 12.9780, 77.6012, "KM 14/2"),
        ("MISSING_FASTENER", "S1", "RESOLVED", "AMRIN_02", .82, 12.9792, 77.6021, "KM 14/3"),
        ("CRACK", "S2", "ACTIVE", "AMRIN_03", .88, 12.9800, 77.6034, "KM 14/4"),
    ]
    alert_ids = [f"ALT_DEMO_{index:03d}" for index in range(1, len(examples) + 1)]
    defect_ids = [f"DEF_DEMO_{index:03d}" for index in range(1, len(examples) + 1)]
    task_specs = [(2, "USR_WORKER", "ASSIGNED"), (3, "USR_WORKER", "IN_PROGRESS"),
                  (5, "USR_WORKER", "COMPLETED"), (8, "USR_WORKER", "ACCEPTED"),
                  (10, None, "ASSIGNED")]
    decisions = [
        ("DEC_DEMO_001", "TRAIN_01", "SW_01", "TRACK_A", "TRACK_A", "Both routes clear; continue on Track A.", .98, 0),
        ("DEC_DEMO_002", "TRAIN_01", "SW_01", "TRACK_A", "TRACK_B", "Critical defect on Track A; Track B is clear.", .92, 0),
        ("DEC_DEMO_003", "TRAIN_02", "SW_02", "TRACK_B", "TRACK_B", "Track A has a moderate defect and Track C is occupied; hold route with warning.", .74, 0),
        ("DEC_DEMO_004", "TRAIN_01", "SW_01", "TRACK_A", None, "Both routes have critical defects; emergency stop.", .99, 1),
        ("DEC_DEMO_005", "TRAIN_02", "SW_02", "TRACK_C", "TRACK_B", "Historical resolved maintenance case; Track B selected.", .88, 0),
    ]

    with connection() as conn:
        for item in devices:
            conn.execute("INSERT OR IGNORE INTO device(device_id,device_name,location,status,last_seen,created_at) VALUES (?,?,?,?,?,?)", item)
        for item in sensors:
            conn.execute("INSERT OR IGNORE INTO sensor(sensor_id,device_id,sensor_type,sampling_rate,status,created_at) VALUES (?,?,?,?,?,?)",
                         (*item, "OFFLINE", now))
        for item in users:
            conn.execute("INSERT OR IGNORE INTO app_user(user_id,name,email,role,phone,status) VALUES (?,?,?,?,?,?)", item)
        for item in tracks:
            conn.execute("INSERT OR IGNORE INTO track(track_id,track_name,status,occupancy,max_speed) VALUES (?,?,?,?,?)", item)
        for item in switches:
            conn.execute("INSERT OR IGNORE INTO track_switch(switch_id,from_track,to_track,current_state,status) VALUES (?,?,?,?,?)", item)
        for item in trains:
            conn.execute("INSERT OR IGNORE INTO train(train_id,train_name,current_track,speed,position,destination,status) VALUES (?,?,?,?,?,?,?)", item)

        for index, (kind, severity, status, device, confidence, lat, lng, chainage) in enumerate(examples):
            number = index + 1
            created = f"2026-10-{max(1, 18 - index):02d}T08:30:00.000Z"
            priority = {"S1": "LOW", "S2": "MEDIUM", "S3": "CRITICAL"}[severity]
            sensor_id = "CAM_01" if device == "AMRIN_01" else None
            conn.execute(
                """INSERT OR IGNORE INTO defect(defect_id,device_id,sensor_id,defect_type,confidence,severity,
                   latitude,longitude,chainage,timestamp,image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (defect_ids[index], device, sensor_id, kind, confidence, severity, lat, lng, chainage,
                 created, f"/images/demo-{number:02d}.jpg"),
            )
            resolved_at = created if status == "RESOLVED" else None
            conn.execute(
                "INSERT OR IGNORE INTO alert(alert_id,defect_id,priority,status,created_at,resolved_at) VALUES (?,?,?,?,?,?)",
                (alert_ids[index], defect_ids[index], priority, status, created, resolved_at),
            )
        for index, (example_number, worker_id, task_status) in enumerate(task_specs, start=1):
            alert_id = alert_ids[example_number - 1]
            created = f"2026-10-{max(1, 18 - example_number):02d}T09:00:00.000Z"
            started = created if task_status in {"IN_PROGRESS", "COMPLETED"} else None
            completed = created if task_status == "COMPLETED" else None
            priority = {"S1": "LOW", "S2": "MEDIUM", "S3": "CRITICAL"}[examples[example_number - 1][1]]
            conn.execute(
                """INSERT OR IGNORE INTO maintenance_task(task_id,alert_id,assigned_worker_id,priority,status,
                   assigned_at,started_at,completed_at,remarks) VALUES (?,?,?,?,?,?,?,?,?)""",
                (f"TASK_DEMO_{index:03d}", alert_id, worker_id, priority, task_status, created, started,
                 completed, "Seeded demonstration task"),
            )
            seeded_alert_status = {
                "ASSIGNED": "ASSIGNED", "ACCEPTED": "ASSIGNED",
                "IN_PROGRESS": "IN_PROGRESS", "COMPLETED": "RESOLVED",
            }[task_status]
            conn.execute(
                "UPDATE alert SET status=?,resolved_at=CASE WHEN ?='RESOLVED' THEN ? ELSE resolved_at END WHERE alert_id=?",
                (seeded_alert_status, seeded_alert_status, completed, alert_id),
            )
        for item in decisions:
            conn.execute(
                """INSERT OR IGNORE INTO switch_decision(decision_id,train_id,switch_id,current_track,selected_track,
                   reason,confidence,emergency_stop,timestamp) VALUES (?,?,?,?,?,?,?,?,?)""",
                (*item, now),
            )

        for device_id, _name, _location, status, last_seen in devices:
            queue_firebase_sync(conn, f"/devices/{device_id}", {"status": status, "last_seen": last_seen})
        for index, alert_id in enumerate(alert_ids):
            row = conn.execute(f"{ALERT_SELECT} WHERE a.alert_id=?", (alert_id,)).fetchone()
            if row:
                queue_firebase_sync(conn, f"/alerts/{alert_id}", _alert(row))
        for index, (example_number, _worker, _task_status) in enumerate(task_specs, start=1):
            record = conn.execute("SELECT * FROM maintenance_task WHERE task_id=?", (f"TASK_DEMO_{index:03d}",)).fetchone()
            if record:
                queue_firebase_sync(conn, f"/tasks/TASK_DEMO_{index:03d}", dict(record))
        summary = compute_summary(conn)
        queue_firebase_sync(conn, "/dashboard_summary", summary)
        latest_decision = conn.execute(
            "SELECT * FROM switch_decision ORDER BY timestamp DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if latest_decision:
            decision = dict(latest_decision)
            decision["emergency_stop"] = bool(decision["emergency_stop"])
            current_track = decision["current_track"] if decision["emergency_stop"] else (
                decision["selected_track"] or decision["current_track"]
            )
            queue_firebase_sync(conn, "/switch_status", {"current_track": current_track, "last_decision": decision})

    print("Database seeded (idempotent).")
    print("Devices: 3 | Sensors: 5 | Alerts: 10 | Tasks: 5 | Users: 2 | Trains: 2 | Tracks: 3 | Switches: 2 | Decisions: 5")


if __name__ == "__main__":
    seed()

