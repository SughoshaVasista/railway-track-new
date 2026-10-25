from fastapi import APIRouter, status

from app.schemas.common import ApiResponse
from app.schemas.entities import DeviceCreate, DeviceHeartbeat, DeviceHealth, DeviceOut
from app.services import device_service

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.post("", response_model=ApiResponse[DeviceOut], status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate):
    return ApiResponse(data=device_service.create_device(payload))


@router.get("", response_model=ApiResponse[list[DeviceOut]])
def list_devices():
    return ApiResponse(data=device_service.list_devices())


@router.get("/{device_id}/status", response_model=ApiResponse[DeviceHealth])
def get_device_status(device_id: str):
    return ApiResponse(data=device_service.get_health(device_id))


@router.post("/{device_id}/heartbeat", response_model=ApiResponse[DeviceOut])
def heartbeat(device_id: str, payload: DeviceHeartbeat):
    return ApiResponse(data=device_service.heartbeat(device_id, payload.timestamp, payload.location))

