from fastapi import APIRouter, Query, status

from app.schemas.common import ApiResponse
from app.schemas.entities import SensorCreate, SensorOut, SensorReadingsBatch, SensorReadingOut
from app.services import sensor_service

router = APIRouter(prefix="/api/sensors", tags=["sensors"])


@router.post("", response_model=ApiResponse[SensorOut], status_code=status.HTTP_201_CREATED)
def register_sensor(payload: SensorCreate):
    return ApiResponse(data=sensor_service.register_sensor(payload))


@router.post("/readings", response_model=ApiResponse[dict])
def create_readings(payload: SensorReadingsBatch):
    return ApiResponse(data=sensor_service.create_readings(payload))


@router.get("/latest", response_model=ApiResponse[list[SensorReadingOut]])
def get_latest_readings(device_id: str | None = Query(default=None, max_length=80)):
    return ApiResponse(data=sensor_service.latest_readings(device_id))

