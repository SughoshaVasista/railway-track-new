from io import BytesIO
from uuid import uuid4

from fastapi import APIRouter, File, Form, Query, Request, UploadFile, status
from PIL import Image, UnidentifiedImageError

from app.schemas.common import ApiResponse, Page
from app.schemas.entities import TaskCreate, TaskOut, TaskStatus, TaskStatusUpdate, TaskUpdate
from app.services import task_service
from app.database import connection, queue_firebase_sync
from app.services.common import ServiceError

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


@router.post("/{task_id}/evidence", response_model=ApiResponse[dict])
async def upload_task_evidence(
    task_id: str,
    request: Request,
    file: UploadFile = File(...),
    notes: str = Form(default=""),
):
    settings = request.app.state.settings
    if file.content_type and not file.content_type.startswith("image/"):
        raise ServiceError("Repair evidence must be an image", 415)
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    await file.close()
    if not content:
        raise ServiceError("Uploaded image is empty", 400)
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise ServiceError(f"Image exceeds {settings.max_upload_mb} MB limit", 413)
    try:
        image = Image.open(BytesIO(content))
        if image.width * image.height > 20_000_000:
            raise ServiceError("Image dimensions exceed the 20 megapixel limit", 413)
        image.verify()
        image_format = (image.format or "JPEG").lower()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ServiceError("Uploaded file is not a valid image", 400) from exc
    extension = "jpg" if image_format == "jpeg" else image_format
    if extension not in {"jpg", "png", "webp", "gif", "bmp", "tiff"}:
        raise ServiceError("Unsupported image format", 415)
    evidence_dir = settings.database_path.parent / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.{extension}"
    (evidence_dir / filename).write_bytes(content)
    image_url = f"{str(request.base_url).rstrip('/')}/media/{filename}"
    with connection() as conn:
        current = conn.execute("SELECT * FROM maintenance_task WHERE task_id=?", (task_id,)).fetchone()
        if not current:
            (evidence_dir / filename).unlink(missing_ok=True)
            raise ServiceError(f"Task '{task_id}' not found", 404)
        if current["status"] != "IN_PROGRESS":
            (evidence_dir / filename).unlink(missing_ok=True)
            raise ServiceError("Evidence can only be submitted while a task is in progress", 409)
        remarks = "\n".join(part for part in (current["remarks"], notes.strip()) if part) or None
        conn.execute("UPDATE maintenance_task SET completion_image=?,remarks=? WHERE task_id=?", (image_url, remarks, task_id))
        record = task_service._task_view(conn, conn.execute("SELECT * FROM maintenance_task WHERE task_id=?", (task_id,)).fetchone())
        queue_firebase_sync(conn, f"/tasks/{task_id}", record)
    return ApiResponse(data={"task_id": task_id, "status": "RECEIVED", "image_url": image_url, "task": record})

