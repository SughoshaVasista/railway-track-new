from fastapi import APIRouter, status

from app.schemas.common import ApiResponse
from app.schemas.entities import SwitchDecisionCreate, SwitchDecisionOut, SwitchStatus
from app.services import switch_service

router = APIRouter(prefix="/api/switch", tags=["rail simulation"])


@router.post("/decision", response_model=ApiResponse[SwitchDecisionOut], status_code=status.HTTP_201_CREATED)
def create_decision(payload: SwitchDecisionCreate):
    return ApiResponse(data=switch_service.create_decision(payload))


@router.get("/status", response_model=ApiResponse[dict])
def get_switch_status():
    current = switch_service.get_status()
    decision = current.get("last_decision")
    return ApiResponse(data={
        **current,
        "status": "NO_DATA" if not decision else ("EMERGENCY_STOP" if decision.get("emergency_stop") else "DECISION_RECORDED"),
        "action": "EMERGENCY_STOP" if decision and decision.get("emergency_stop") else ("MAINTAIN" if not decision else "ROUTE_SELECTED"),
        "action_level": "CRITICAL" if decision and decision.get("emergency_stop") else "INFO",
        "train_id": decision.get("train_id") if decision else None,
        "switch_id": decision.get("switch_id") if decision else None,
        "target_track": decision.get("selected_track") if decision else None,
        "confidence": decision.get("confidence") if decision else None,
        "reason": decision.get("reason") if decision else "No switch decision has been recorded.",
        "rules_checked": [],
        "raw_scores": {},
    })


@router.get("/tracks", response_model=ApiResponse[list[dict]])
def list_tracks():
    return ApiResponse(data=switch_service.list_tracks())

