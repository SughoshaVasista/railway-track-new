import hashlib
import hmac
from datetime import timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.errors import AppError
from app.models import Alert, AlertHistory, Device, EventLog, MlOriginEvent
from app.models.entities import utc_now
from app.schemas.ml import MlEventRequest

router = APIRouter(prefix="/api/integrations/ml", tags=["ml-ingestion"])


@router.post("/events", status_code=201)
def ingest_event(
    payload: MlEventRequest,
    request: Request,
    x_ml_api_key: str | None = Header(default=None, alias="X-ML-API-Key"),
    db: Session = Depends(get_db),
):
    configured_token = request.app.state.settings.ml_ingest_token
    if not configured_token:
        raise AppError(503, "ml_ingestion_not_configured", "ML ingestion is disabled until ML_INGEST_TOKEN is configured")
    if not x_ml_api_key or not hmac.compare_digest(x_ml_api_key, configured_token):
        raise AppError(401, "invalid_ml_api_key", "A valid ML API key is required")

    namespace = hashlib.sha256(f"{payload.source}:{payload.device_id}".encode()).hexdigest()
    existing = db.scalar(select(MlOriginEvent).where(
        MlOriginEvent.source_namespace == namespace,
        MlOriginEvent.source_event_id == payload.source_event_id,
    ))
    if existing:
        return {"event_id": existing.id, "alert_id": existing.alert_id, "duplicate": True}

    device = db.get(Device, payload.device_id)
    if device is None:
        raise AppError(422, "unknown_device", "device_id must refer to a registered device")

    alert_id = f"ALT-{uuid4().hex}"
    alert_source_event_id = hashlib.sha256(f"{namespace}:{payload.source_event_id}".encode()).hexdigest()
    detected_at = payload.detected_at.astimezone(timezone.utc)
    evidence = payload.model_dump(mode="json", exclude_none=True)
    gps = {"accuracy_m": payload.gps_accuracy_m} if payload.gps_accuracy_m is not None else None
    try:
        alert = Alert(
            id=alert_id,
            defect=payload.defect,
            severity=payload.severity,
            status="DETECTED",
            confidence=payload.confidence,
            track=payload.track,
            chainage=payload.chainage,
            latitude=payload.latitude,
            longitude=payload.longitude,
            gps_metadata=gps,
            sensors=payload.sensor_fusion,
            source="ml_backend",
            source_event_id=alert_source_event_id,
            city=payload.city or device.city,
            detected_at=detected_at,
        )
        event = MlOriginEvent(
            id=f"MLE-{uuid4().hex}",
            source_namespace=namespace,
            source_event_id=payload.source_event_id,
            device_id=device.id,
            alert_id=alert_id,
            model_version=payload.model_version,
            inference_ms=payload.inference_ms,
            payload={"schema_version": payload.schema_version, "detection": evidence},
            detected_at=detected_at,
        )
        db.add_all([
            alert,
            event,
            AlertHistory(
                alert_id=alert_id,
                action="ml_detection_ingested",
                new_status="DETECTED",
                changes={"source": "ml_backend", "source_event_id": payload.source_event_id},
                source="ml_backend",
                timestamp=utc_now(),
            ),
            EventLog(
                action="ml_detection_ingested",
                object_type="alert",
                object_id=alert_id,
                summary=f"ML detection recorded: {payload.defect} ({payload.severity})",
                details={"source": payload.source, "device_id": device.id, "event_id": payload.source_event_id},
                source="ml_backend",
                timestamp=utc_now(),
            ),
        ])
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(MlOriginEvent).where(
            MlOriginEvent.source_namespace == namespace,
            MlOriginEvent.source_event_id == payload.source_event_id,
        ))
        if existing:
            return {"event_id": existing.id, "alert_id": existing.alert_id, "duplicate": True}
        raise AppError(500, "ml_event_persist_failed", "The ML event could not be persisted") from None
    except Exception:
        db.rollback()
        raise
    return {"event_id": event.id, "alert_id": alert_id, "duplicate": False}
