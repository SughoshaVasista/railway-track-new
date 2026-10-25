from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.services.common import ServiceError

logger = logging.getLogger(__name__)


class ModelManager:
    """Loads the configured Ultralytics model once and serializes prediction calls."""

    def __init__(self, model_path: Path):
        self.model_path = model_path
        self._model = None
        self._lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._active_inferences = 0
        self._last_inference_ms = None
        self._last_inference_at = None

    def status(self, imgsz: int) -> dict:
        with self._status_lock:
            inference_active = self._active_inferences > 0
            last_inference_ms = self._last_inference_ms
            last_inference_at = self._last_inference_at
        model = self._model
        names = getattr(model, "names", None) if model is not None else None
        weights_available = self.model_path.is_file()
        return {
            "status": "ready" if weights_available else "missing_weights",
            "name": self.model_path.name,
            "weights_available": weights_available,
            "loaded": model is not None,
            "runtime_version": None,
            "class_count": len(names) if names is not None else None,
            "input_size": imgsz,
            "inference_active": inference_active,
            "inference_ms": last_inference_ms,
            "last_inference_at": last_inference_at,
            "device": str(getattr(model, "device", "unknown")) if model is not None else None,
        }

    def _load(self):
        if self._model is not None:
            return self._model
        with self._lock:
            if self._model is not None:
                return self._model
            if not self.model_path.is_file():
                raise ServiceError(
                    f"Model weights are missing at {self.model_path}. Train the model or set MODEL_PATH.", 503
                )
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise ServiceError("Install the ML dependencies from ml/requirements.txt to enable inference", 503) from exc
            try:
                self._model = YOLO(str(self.model_path))
            except Exception as exc:
                logger.exception("Failed to load model weights")
                raise ServiceError("Configured model weights could not be loaded", 503) from exc
        return self._model

    def predict(self, image, confidence: float, iou: float = 0.55, imgsz: int = 960) -> dict:
        started_at = time.perf_counter()
        with self._status_lock:
            self._active_inferences += 1
        try:
            model = self._load()
            with self._lock:
                result = model.predict(source=image, conf=confidence, iou=iou, imgsz=imgsz, verbose=False)[0]
            names = result.names
            detections = []
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    class_id = int(box.cls.item())
                    class_name = str(names[class_id])
                    class_key = class_name.strip().lower().replace("-", "_").replace(" ", "_")
                    type_map = {
                        "crack": "CRACK", "railway_crack": "CRACK", "railway_cracks": "CRACK",
                        "rust": "RUST", "joint_gap": "JOINT_GAP",
                        "missing_fastener": "MISSING_FASTENER", "railway_gap": "RAILWAY_GAP",
                    }
                    coordinates = [float(value) for value in box.xyxy[0].tolist()]
                    detections.append({
                        "class_name": class_name,
                        "defect_type": type_map.get(class_key),
                        "confidence": float(box.conf.item()),
                        "bbox": dict(zip(("x1", "y1", "x2", "y2"), coordinates)),
                    })
            height, width = result.orig_shape
            return {
                "image_width": int(width), "image_height": int(height),
                "model": self.model_path.name, "detections": detections,
            }
        except ServiceError:
            raise
        except Exception as exc:
            logger.exception("Model prediction failed")
            raise ServiceError("Model prediction failed for this image", 422) from exc
        finally:
            with self._status_lock:
                self._active_inferences -= 1
                self._last_inference_ms = round((time.perf_counter() - started_at) * 1000, 2)
                self._last_inference_at = datetime.now(timezone.utc).isoformat()
