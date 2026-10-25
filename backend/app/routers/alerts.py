from fastapi import APIRouter, Query

from app.schemas.common import ApiResponse, Page
from app.schemas.entities import AlertCreate, AlertOut, AlertStatus, AlertStatusUpdate, Severity
from app.services import alert_service

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("", response_model=ApiResponse[AlertOut], status_code=201)
def create_alert(payload: AlertCreate):
    return ApiResponse(data=alert_service.create_alert(payload))


@router.get("", response_model=ApiResponse[Page[AlertOut]])
def list_alerts(
    status: AlertStatus | None = None,
    severity: Severity | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return ApiResponse(data=alert_service.list_alerts(status.value if status else None,
        severity.value if severity else None, limit, offset))


@router.get("/{alert_id}", response_model=ApiResponse[AlertOut])
def get_alert(alert_id: str):
    return ApiResponse(data=alert_service.get_alert(alert_id))


@router.put("/{alert_id}/status", response_model=ApiResponse[AlertOut])
def update_alert_status(alert_id: str, payload: AlertStatusUpdate):
    return ApiResponse(data=alert_service.update_status(alert_id, payload.status.value))

