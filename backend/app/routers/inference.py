from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.schemas.common import ApiResponse
from app.schemas.entities import InferenceResult
from app.services.common import ServiceError

router = APIRouter(prefix="/api/inference", tags=["ML inference"])


@router.get("/status", response_model=ApiResponse[dict])
def model_status(request: Request):
    settings = request.app.state.settings
    return ApiResponse(data=request.app.state.model_manager.status(settings.inference_imgsz))


@router.post("/detect", response_model=ApiResponse[InferenceResult])
async def detect_image(
    request: Request,
    file: UploadFile = File(...),
    confidence: float | None = Query(default=None, ge=0, le=1),
    iou: float | None = Query(default=None, ge=0, le=1),
    imgsz: int | None = Query(default=None, ge=32, le=4096),
):
    settings = request.app.state.settings
    confidence = settings.inference_confidence if confidence is None else confidence
    iou = settings.inference_iou if iou is None else iou
    imgsz = settings.inference_imgsz if imgsz is None else imgsz
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=415, detail="Upload must be an image")
    contents = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    await file.close()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded image is empty")
    if len(contents) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Image exceeds {settings.max_upload_mb} MB limit")
    try:
        image = Image.open(BytesIO(contents))
        if image.width * image.height > 20_000_000:
            raise HTTPException(status_code=413, detail="Image dimensions exceed the 20 megapixel limit")
        image.verify()
        image = Image.open(BytesIO(contents)).convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image") from exc
    try:
        result = await run_in_threadpool(request.app.state.model_manager.predict, image, confidence, iou, imgsz)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return ApiResponse(data=result)
