from fastapi import APIRouter, Query, status

from app.schemas.common import ApiResponse, Page
from app.schemas.entities import TaskCreate, TaskOut, TaskStatus, TaskStatusUpdate, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["maintenance tasks"])


@router.post("", response_model=ApiResponse[TaskOut], status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate):
    return ApiResponse(data=task_service.create_task(payload))


@router.get("", response_model=ApiResponse[Page[TaskOut]])
def list_tasks(
    worker_id: str | None = Query(default=None, max_length=80),
    task_status: TaskStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return ApiResponse(data=task_service.list_tasks(
        worker_id, task_status.value if task_status else None, limit, offset
    ))


@router.get("/{task_id}", response_model=ApiResponse[TaskOut])
def get_task(task_id: str):
    return ApiResponse(data=task_service.get_task(task_id))


@router.put("/{task_id}", response_model=ApiResponse[TaskOut])
def update_task(task_id: str, payload: TaskUpdate):
    return ApiResponse(data=task_service.update_task(task_id, payload))


@router.put("/{task_id}/status", response_model=ApiResponse[TaskOut])
def update_task_status(task_id: str, payload: TaskStatusUpdate):
    return ApiResponse(data=task_service.update_status(task_id, payload))

