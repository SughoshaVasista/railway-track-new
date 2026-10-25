from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.schemas.entities import DashboardSummary
from app.services.dashboard_service import get_summary

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=ApiResponse[DashboardSummary])
def dashboard_summary():
    return ApiResponse(data=get_summary())

