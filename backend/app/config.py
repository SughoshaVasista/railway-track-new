from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_path: Path
    api_key: str | None
    cors_origins: tuple[str, ...]
    max_upload_mb: int
    model_path: Path
    inference_confidence: float
    inference_iou: float
    inference_imgsz: int
    firebase_database_url: str | None
    firebase_credentials: Path | None
    roboflow_api_key: str | None
    roboflow_workspace: str
    roboflow_project: str
    roboflow_version: int

    @property
    def firebase_enabled(self) -> bool:
        return bool(self.firebase_database_url and self.firebase_credentials)


def get_settings() -> Settings:
    origins = tuple(
        item.strip().rstrip("/")
        for item in os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        ).split(",")
        if item.strip()
    )
    credentials = os.getenv("FIREBASE_CREDENTIALS", "").strip()
    model_path = Path(os.getenv("MODEL_PATH", "models/best.pt")).expanduser().resolve()
    threshold_path = Path(os.getenv("MODEL_THRESHOLD_PATH", "models/threshold.json")).expanduser().resolve()
    calibrated_confidence, calibrated_iou = 0.25, 0.55
    try:
        calibration = json.loads(threshold_path.read_text(encoding="utf-8"))
        selected = calibration.get("selected") or {}
        if selected and model_path.is_file() and calibration.get("model_sha256"):
            digest = hashlib.sha256()
            with model_path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() == calibration["model_sha256"]:
                calibrated_confidence = float(selected["confidence"])
                calibrated_iou = float(calibration.get("nms_iou", calibrated_iou))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    inference_confidence = float(os.getenv("INFERENCE_CONFIDENCE", str(calibrated_confidence)))
    inference_iou = float(os.getenv("INFERENCE_IOU", str(calibrated_iou)))
    inference_imgsz = int(os.getenv("INFERENCE_IMGSZ", "960"))
    if not 0 <= inference_confidence <= 1 or not 0 <= inference_iou <= 1:
        raise ValueError("INFERENCE_CONFIDENCE and INFERENCE_IOU must be within [0, 1].")
    if not 32 <= inference_imgsz <= 4096:
        raise ValueError("INFERENCE_IMGSZ must be between 32 and 4096 pixels.")
    return Settings(
        app_env=os.getenv("APP_ENV", "development").strip().lower(),
        database_path=Path(os.getenv("DATABASE_PATH", "data/railway.db")).expanduser().resolve(),
        api_key=os.getenv("API_KEY") or None,
        cors_origins=origins,
        max_upload_mb=max(1, int(os.getenv("MAX_UPLOAD_MB", "10"))),
        model_path=model_path,
        inference_confidence=inference_confidence,
        inference_iou=inference_iou,
        inference_imgsz=inference_imgsz,
        firebase_database_url=os.getenv("FIREBASE_DATABASE_URL") or None,
        firebase_credentials=Path(credentials).expanduser().resolve() if credentials else None,
        roboflow_api_key=os.getenv("ROBOFLOW_API_KEY") or None,
        roboflow_workspace=os.getenv("ROBOFLOW_WORKSPACE", "thesis-group"),
        roboflow_project=os.getenv("ROBOFLOW_PROJECT", "railway-crack-detection"),
        roboflow_version=int(os.getenv("ROBOFLOW_VERSION", "15")),
    )

