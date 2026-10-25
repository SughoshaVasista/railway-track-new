"""Idempotent development-only sample records. No sample is live telemetry."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Alert,
    AlertHistory,
    DecisionState,
    Device,
    EventLog,
    MaintenanceTask,
    SensorReading,
    Track,
    Train,
    User,
)
from app.models.entities import utc_now

DEMO_SOURCE = "demo"


def _add_if_missing(session: Session, model, public_id: str, **values) -> bool:
    if session.get(model, public_id) is not None:
        return False
    session.add(model(id=public_id, **values))
    return True


def seed_demo(session: Session) -> dict[str, int]:
    """Insert stable sample records once; caller owns the surrounding transaction."""
    counts: dict[str, int] = {}
    now = utc_now()

    counts["users"] = int(_add_if_missing(
        session,
        User,
        "worker-01",
        worker_id="worker-01",
        name="Maintenance Worker",
        email="worker-01@demo.invalid",
        username="worker-01",
        password_hash=None,
        role="worker",
        approval_status="approved",
        city="bengaluru",
        is_active=True,
        source=DEMO_SOURCE,
    ))
    counts["devices"] = int(_add_if_missing(
        session,
        Device,
        "device-01",
        name="AMRIN-DEMO-01",
        platform="Raspberry Pi 5 (demo record)",
        status="ONLINE",
        city="bengaluru",
        uptime="DEMO 3d 04h",
        network_status="ONLINE",
        pi_status="ONLINE",
        diagnostics={"source": DEMO_SOURCE, "checks": [{"name": "Demo sensor bus", "status": "PASS"}]},
        source=DEMO_SOURCE,
    ))
    counts["tracks"] = sum([
        _add_if_missing(session, Track, "track-a", name="Track A", status="OPEN", occupancy="CLEAR", max_speed="80 km/h", severity="S3", city="bengaluru", source=DEMO_SOURCE, geometry={"type": "LineString", "coordinates": [[77.5928, 12.9708], [77.5960, 12.9730], [77.5990, 12.9752]]}),
        _add_if_missing(session, Track, "track-b", name="Track B", status="OPEN", occupancy="OCCUPIED", max_speed="60 km/h", severity="S2", city="bengaluru", source=DEMO_SOURCE, geometry={"type": "LineString", "coordinates": [[77.5928, 12.9698], [77.5960, 12.9720], [77.5990, 12.9742]]}),
    ])
    counts["trains"] = int(_add_if_missing(
        session,
        Train,
        "train-demo-01",
        latitude=12.9713,
        longitude=77.5938,
        speed="42 km/h",
        destination="KSR Bengaluru",
        next_switch="switch-01",
        distance="680 m",
        gps_metadata={"accuracy": 3.1, "satellites": 8, "fix_type": "3D"},
        city="bengaluru",
        source=DEMO_SOURCE,
        measured_at=now,
    ))
    session.flush()

    alert_rows = [
        ("ALT-102", "Crack", "S3", "ACTIVE", "Track A", "KM 12/4", 12.9719, 77.5942, 0.94),
        ("ALT-103", "Joint Gap", "S2", "ASSIGNED", "Track B", "KM 13/2", 12.9732, 77.5961, 0.87),
        ("ALT-104", "Surface Wear", "S1", "RESOLVED", "Track A", "KM 13/8", 12.9745, 77.5980, 0.81),
        ("ALT-105", "Fastener Issue", "S2", "ACKNOWLEDGED", "Track B", "KM 14/1", 12.9754, 77.5992, 0.76),
        ("ALT-106", "Track Obstruction", "S1", "DETECTED", "Track A", "KM 14/6", 12.9762, 77.6001, 0.69),
    ]
    counts["alerts"] = 0
    for index, (public_id, defect, severity, status, track, chainage, lat, lng, confidence) in enumerate(alert_rows):
        counts["alerts"] += int(_add_if_missing(
            session,
            Alert,
            public_id,
            defect=defect,
            severity=severity,
            status=status,
            confidence=confidence,
            track=track,
            chainage=chainage,
            latitude=lat,
            longitude=lng,
            gps_metadata={"accuracy": 3.0, "fix_type": "3D"},
            sensors=[{"name": "Camera", "status": "DEMO ONLY"}, {"name": "Ultrasonic", "status": "DEMO ONLY"}],
            source=DEMO_SOURCE,
            city="bengaluru",
            assigned_worker_user_id="worker-01" if status == "ASSIGNED" else None,
            detected_at=now - timedelta(minutes=5 * (index + 1)),
        ))
    session.flush()

    counts["tasks"] = int(_add_if_missing(
        session,
        MaintenanceTask,
        "TASK-001",
        alert_id="ALT-103",
        assigned_worker_user_id="worker-01",
        status="ASSIGNED",
        priority="S2",
        admin_notes="Demo task record for UI walkthrough.",
        source=DEMO_SOURCE,
    ))
    counts["alert_history"] = int(_add_if_missing(
        session,
        AlertHistory,
        "HIST-DEMO-001",
        alert_id="ALT-103",
        actor_user_id="worker-01",
        action="DEMO_TASK_ASSIGNED",
        old_status="ACKNOWLEDGED",
        new_status="ASSIGNED",
        changes={"source": DEMO_SOURCE},
        notes="Seeded demo history entry.",
        timestamp=now,
        source=DEMO_SOURCE,
    ))
    counts["sensor_readings"] = 0
    sensor_rows = [
        {"name": "Camera", "status": "ONLINE", "text_value": "DEMO FRAME 18420", "interpreted_value": "Demo camera record"},
        {"name": "Ultrasonic", "status": "ONLINE", "numeric_value": 18.4, "unit": "mm gap", "interpreted_value": "Demo gap reading"},
        {"name": "Accelerometer", "status": "DEGRADED", "numeric_value": 0.42, "x": 0.12, "y": 0.08, "z": 0.42, "vibration": "DEMO ABNORMAL", "anomaly_score": 0.72},
        {"name": "Temperature", "status": "ONLINE", "numeric_value": 34.6, "unit": "C", "interpreted_value": "Demo reading"},
        {"name": "GPS", "status": "ONLINE", "latitude": 12.9724, "longitude": 77.5950, "gps_accuracy": 2.8, "satellites": 8, "fix_type": "3D"},
    ]
    for sensor in sensor_rows:
        exists = session.scalar(select(SensorReading.id).where(
            SensorReading.device_id == "device-01",
            SensorReading.name == sensor["name"],
            SensorReading.source == DEMO_SOURCE,
        ).limit(1))
        if not exists:
            session.add(SensorReading(device_id="device-01", recorded_at=now, source=DEMO_SOURCE, **sensor))
            counts["sensor_readings"] += 1
    counts["decision_states"] = int(_add_if_missing(
        session,
        DecisionState,
        "latest",
        status="READY",
        action="MAINTAIN",
        action_level="WARNING",
        train_id="train-demo-01",
        switch_id="switch-01",
        target_track="Track A",
        confidence=0.78,
        reason="Demo recommendation only; no hardware is controlled.",
        latitude=12.9720,
        longitude=77.5954,
        rules_checked=[
            {"rule": "Target track is not occupied", "passed": True},
            {"rule": "No S3 defect on target track", "passed": True},
            {"rule": "Switch mechanism is available", "passed": True},
            {"rule": "Train is not too close to switch", "passed": True},
        ],
        raw_scores={"A": 0.78, "B": 0.42},
        payload={"demo": True},
        source=DEMO_SOURCE,
    ))
    counts["event_log"] = int(_add_if_missing(
        session,
        EventLog,
        "EVT-DEMO-001",
        action="DEMO_SEED_CREATED",
        object_type="system",
        object_id="demo-seed",
        summary="Development sample data; not live telemetry.",
        details={"source": DEMO_SOURCE},
        source=DEMO_SOURCE,
        timestamp=now,
    ))
    session.flush()
    return counts
