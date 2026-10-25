from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def locate_split(data: dict, yaml_path: Path, split: str) -> tuple[Path, Path]:
    root = Path(data.get("path", yaml_path.parent))
    if not root.is_absolute():
        root = (yaml_path.parent / root).resolve()
    value = Path(str(data[split]))
    image_dir = value if value.is_absolute() else root / value
    if not image_dir.is_dir():
        alias = "valid" if split == "val" else split
        image_dir = root / alias / "images"
    if not image_dir.is_dir():
        raise SystemExit(f"{split} image directory not found: {image_dir}")
    labels_dir = image_dir.parent / "labels" if image_dir.name == "images" else image_dir / "labels"
    return image_dir, labels_dir


def read_ground_truth(label_path: Path, width: int, height: int) -> list[list[float]]:
    if not label_path.is_file():
        raise SystemExit(f"Missing label file (use an empty file for a true background image): {label_path}")
    rows = [line.split() for line in label_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    boxes = []
    for row in rows:
        if len(row) != 5:
            raise SystemExit(f"Malformed YOLO detection label: {label_path}")
        class_id = int(float(row[0]))
        xc, yc, box_width, box_height = map(float, row[1:])
        if class_id != 0:
            continue
        boxes.append([
            (xc - box_width / 2) * width,
            (yc - box_height / 2) * height,
            (xc + box_width / 2) * width,
            (yc + box_height / 2) * height,
        ])
    return boxes


def box_iou(box: list[float], boxes: list[list[float]]) -> list[float]:
    values = []
    area_a = max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
    for other in boxes:
        x1, y1 = max(box[0], other[0]), max(box[1], other[1])
        x2, y2 = min(box[2], other[2]), min(box[3], other[3])
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        area_b = max(0.0, other[2] - other[0]) * max(0.0, other[3] - other[1])
        values.append(intersection / max(area_a + area_b - intersection, 1e-9))
    return values


def score_threshold(
    per_image: list[tuple[list[list[float]], list[list[float]], list[float]]],
    confidence: float,
    match_iou: float,
) -> dict:
    tp = fp = fn = 0
    for ground_truth, predictions, scores in per_image:
        order = sorted((i for i, score in enumerate(scores) if score >= confidence), key=lambda i: scores[i], reverse=True)
        matched: set[int] = set()
        for prediction_index in order:
            overlaps = box_iou(predictions[prediction_index], ground_truth)
            best = max(range(len(overlaps)), key=overlaps.__getitem__) if overlaps else None
            if best is not None and overlaps[best] >= match_iou and best not in matched:
                matched.add(best)
                tp += 1
            else:
                fp += 1
        fn += len(ground_truth) - len(matched)
    return {
        "confidence": round(confidence, 4),
        "precision": tp / max(tp + fp, 1),
        "recall": tp / max(tp + fn, 1),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Choose a YOLO confidence threshold using the validation split only.")
    parser.add_argument("--model", type=Path, default=Path("runs/detect/railway-crack-yolov8s-precision/weights/best.pt"))
    parser.add_argument("--data", type=Path, default=Path("data/datasets/railway-crack-detection-15/data.yaml"))
    parser.add_argument("--target-precision", type=float, default=0.90)
    parser.add_argument("--min-recall", type=float, default=0.42)
    parser.add_argument("--nms-iou", type=float, default=0.55)
    parser.add_argument("--match-iou", type=float, default=0.50)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--max-det", type=int, default=300)
    parser.add_argument("--output", type=Path, default=Path("models/threshold.json"))
    args = parser.parse_args()
    if not 0 <= args.target_precision <= 1 or not 0 <= args.min_recall <= 1:
        raise SystemExit("Precision and recall targets must be in [0, 1].")
    if not 0 <= args.nms_iou <= 1 or not 0 <= args.match_iou <= 1:
        raise SystemExit("IoU values must be in [0, 1].")

    model_path, yaml_path = args.model.resolve(), args.data.resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model checkpoint not found: {model_path}")
    if not yaml_path.is_file():
        raise SystemExit(f"Dataset YAML not found: {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    image_dir, labels_dir = locate_split(data, yaml_path, "val")
    images = sorted(path for path in image_dir.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise SystemExit(f"No validation images found in {image_dir}")

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ML dependencies: pip install -r ml/requirements.txt") from exc

    model = YOLO(str(model_path))
    results = model.predict(
        source=[str(path) for path in images], imgsz=args.imgsz, conf=0.001,
        iou=args.nms_iou, max_det=args.max_det, verbose=False,
    )
    if len(results) != len(images):
        raise SystemExit(f"Expected {len(images)} predictions, received {len(results)}")

    per_image = []
    for image_path, result in zip(images, results):
        height, width = result.orig_shape
        label_path = labels_dir / image_path.relative_to(image_dir).with_suffix(".txt")
        ground_truth = read_ground_truth(label_path, width, height)
        boxes = result.boxes
        predictions = boxes.xyxy.cpu().tolist() if boxes is not None else []
        scores = boxes.conf.cpu().tolist() if boxes is not None else []
        per_image.append((ground_truth, predictions, scores))

    thresholds = [round(step / 100, 2) for step in range(1, 100)]
    rows = [score_threshold(per_image, threshold, args.match_iou) for threshold in thresholds]
    eligible = [row for row in rows if row["precision"] >= args.target_precision and row["recall"] >= args.min_recall]
    selected = max(eligible, key=lambda row: row["recall"]) if eligible else None
    report = {
        "model": str(model_path),
        "model_sha256": sha256_file(model_path),
        "split": "val",
        "images": len(images),
        "nms_iou": args.nms_iou,
        "match_iou": args.match_iou,
        "target_precision": args.target_precision,
        "minimum_recall": args.min_recall,
        "selected": selected,
        "sweep": rows,
        "note": "Threshold selected on validation data. Confirm final performance once on an untouched test set.",
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if selected:
        print(
            f"Selected confidence={selected['confidence']:.2f}, "
            f"validation precision={selected['precision']:.3f}, recall={selected['recall']:.3f}, "
            f"TP={selected['tp']} FP={selected['fp']} FN={selected['fn']}"
        )
    else:
        print("No threshold met both targets; add reviewed hard negatives or improve the model/data.")
    print(f"Threshold sweep saved to {output}")


if __name__ == "__main__":
    main()
