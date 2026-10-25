from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader

from app.config import get_settings
from app.database import check_database, initialize_database
from app.firebase import FirebaseMirror, dispatch_outbox
from app.routers import alerts, dashboard, devices, frontend_compat, inference, sensors, switch, tasks
from app.services.common import ServiceError
from app.services.inference_service import ModelManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def authenticate_api(request: Request, supplied_key: str | None = Security(api_key_header)) -> None:
    if not request.url.path.startswith("/api/"):
        return
    configured_key = request.app.state.settings.api_key
    if configured_key is None:
        if request.app.state.settings.app_env == "production":
            raise HTTPException(status_code=503, detail="API authentication is not configured")
        return
    if supplied_key is None or not secrets.compare_digest(supplied_key.encode("utf-8"), configured_key.encode("utf-8")):
        raise HTTPException(status_code=401, detail="A valid X-API-Key is required")


@asynccontextmanager
async def lifespan(app: FastAPI):
    current_settings = get_settings()
    if current_settings.app_env == "production" and not current_settings.api_key:
        raise RuntimeError("Set API_KEY before starting with APP_ENV=production")
    if current_settings.app_env == "production" and "*" in current_settings.cors_origins:
        raise RuntimeError("Wildcard CORS origins are not allowed in production")
    initialize_database()
    app.state.settings = current_settings
    app.state.model_manager = ModelManager(current_settings.model_path)
    mirror = FirebaseMirror(current_settings)
    app.state.firebase_mirror = mirror
    app.state.sync_stop = asyncio.Event()
    app.state.sync_task = None
    if mirror.enabled:
        app.state.sync_task = asyncio.create_task(dispatch_outbox(mirror, app.state.sync_stop))
        logger.info("Firebase outbox dispatcher enabled")
    else:
        logger.info("Firebase mirror disabled; set FIREBASE_DATABASE_URL and FIREBASE_CREDENTIALS to enable it")
    yield
    if app.state.sync_task:
        app.state.sync_stop.set()
        await app.state.sync_task


app = FastAPI(
    title="Railway Crack Detection API",
    description="SQLite-backed railway defect monitoring API and local YOLO inference service.",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(authenticate_api)],
)
app.state.settings = settings
app.mount("/media", StaticFiles(directory=settings.database_path.parent / "evidence", check_dir=False), name="media")
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)


@app.exception_handler(ServiceError)
async def service_error_handler(_request: Request, exc: ServiceError):
    return JSONResponse(status_code=exc.status_code, content={"success": False, "data": None, "error": exc.message})


@app.exception_handler(HTTPException)
async def http_error_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(status_code=exc.status_code, headers=exc.headers,
                        content={"success": False, "data": None, "error": detail})


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    errors = "; ".join(
        f"{'/'.join(str(part) for part in item['loc'])}: {item['msg']}" for item in exc.errors()
    )
    return JSONResponse(status_code=422, content={"success": False, "data": None, "error": errors})


@app.exception_handler(Exception)
async def unexpected_error_handler(_request: Request, exc: Exception):
    logger.error("Unhandled request error", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(status_code=500, content={"success": False, "data": None, "error": "Internal server error"})


@app.get("/health/live", tags=["health"])
def live_health():
    return {"success": True, "data": {"status": "alive"}, "error": None}


@app.get("/health/ready", tags=["health"])
def ready_health():
    try:
        check_database()
    except Exception as exc:
        logger.exception("Database readiness check failed")
        return JSONResponse(status_code=503, content={"success": False, "data": {"database": "unavailable"}, "error": str(exc)})
    return {"success": True, "data": {"database": "ready"}, "error": None}


for route_module in (alerts, devices, sensors, tasks, switch, dashboard, inference, frontend_compat):
    app.include_router(route_module.router)

