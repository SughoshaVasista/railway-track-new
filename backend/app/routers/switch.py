from fastapi import APIRouter, status

from app.schemas.common import ApiResponse
from app.schemas.entities import SwitchDecisionCreate, SwitchDecisionOut, SwitchStatus
from app.services import switch_service

router = APIRouter(prefix="/api/switch", tags=["rail simulation"])


@router.post("/decision", response_model=ApiResponse[SwitchDecisionOut], status_code=status.HTTP_201_CREATED)
def create_decision(payload: SwitchDecisionCreate):
    return ApiResponse(data=switch_service.create_decision(payload))


@router.get("/status", response_model=ApiResponse[SwitchStatus])
def get_switch_status():
    return ApiResponse(data=switch_service.get_status())


@router.get("/tracks", response_model=ApiResponse[list[dict]])
def list_tracks():
    return ApiResponse(data=switch_service.list_tracks())

