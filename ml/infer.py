from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run image or folder inference and save annotations plus detection CSV.")
    parser.add_argument("--model", type=Path, default=Path("models/best.pt"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("runs/predict/sample_predictions"))
    parser.add_argument("--confidence", type=float, default=None, help="Overrides the calibrated threshold.")
    parser.add_argument("--iou", type=float, default=None, help="Overrides calibrated NMS IoU.")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--threshold-file", type=Path, default=Path("models/threshold.json"))
    args = parser.parse_args()
    model_path, source, output = args.model.resolve(), args.source.resolve(), args.output.resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model weights not found: {model_path}")
    if not source.exists():
        raise SystemExit(f"Source image/folder not found: {source}")
    images = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise SystemExit(f"No supported images found in {source}")
    calibration = {}
    try:
        calibration = json.loads(args.threshold_file.resolve().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        pass
    if calibration.get("model_sha256"):
        digest = hashlib.sha256()
        with model_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != calibration["model_sha256"]:
            print("Calibration file is for a different checkpoint; using fallback inference settings.")
            calibration = {}
    selected = calibration.get("selected") or {}
    confidence = args.confidence if args.confidence is not None else float(selected.get("confidence", 0.25))
    iou = args.iou if args.iou is not None else float(calibration.get("nms_iou", 0.55))
    if not 0 <= confidence <= 1 or not 0 <= iou <= 1:
        raise SystemExit("Confidence and NMS IoU must be within [0, 1].")
    print(f"Inference settings: confidence={confidence:.3f}, NMS IoU={iou:.2f}")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ML dependencies: pip install -r ml/requirements.txt") from exc
    output.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(model_path))
    rows = []
    for index, image_path in enumerate(images, start=1):
        result = model.predict(source=str(image_path), conf=confidence, iou=iou, imgsz=args.imgsz, verbose=False)[0]
        annotated_path = output / f"{index:04d}_{image_path.stem}.jpg"
        result.save(filename=str(annotated_path))
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                xyxy = [float(value) for value in box.xyxy[0].tolist()]
                rows.append([str(image_path), str(result.names[int(box.cls.item())]), float(box.conf.item()), *xyxy])
        print(f"{image_path.name}: {len(boxes) if boxes is not None else 0} detection(s)")
    csv_path = output / "detections.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["image", "class", "confidence", "x1", "y1", "x2", "y2"])
        writer.writerows(rows)
    print(f"Annotated images and detection CSV written to {output}")


if __name__ == "__main__":
    main()

