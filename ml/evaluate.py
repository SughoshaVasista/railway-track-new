from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a YOLO detector and print per-class metrics.")
    parser.add_argument("--model", type=Path, default=Path("runs/detect/railway-crack-yolov8s-precision/weights/best.pt"))
    parser.add_argument("--data", type=Path, default=Path("data/datasets/railway-crack-detection-15/data.yaml"))
    parser.add_argument("--split", choices=("val", "test"), default="test")
    parser.add_argument("--confidence", type=float, default=None, help="Optional operating threshold; omit for normal AP evaluation.")
    parser.add_argument("--iou", type=float, default=0.7, help="NMS IoU used while evaluating predictions.")
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--project", type=Path, default=Path("runs/evaluate"))
    parser.add_argument("--name", default="railway-crack-evaluation")
    args = parser.parse_args()
    if args.confidence is not None and not 0 <= args.confidence <= 1:
        raise SystemExit("Confidence must be in [0, 1].")
    if not 0 <= args.iou <= 1:
        raise SystemExit("NMS IoU must be in [0, 1].")
    model_path, data_path = args.model.resolve(), args.data.resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model checkpoint not found: {model_path}")
    if not data_path.is_file():
        raise SystemExit(f"Dataset YAML not found: {data_path}")
    data = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    names = data.get("names", [])
    if isinstance(names, dict):
        names = [names[key] for key in sorted(names, key=lambda value: int(value))]
    train_path = Path(data.get("train", "train/images"))
    root = Path(data.get("path", data_path.parent))
    if not root.is_absolute():
        root = data_path.parent / root
    train_dir = train_path if train_path.is_absolute() else root / train_path
    image_count = sum(1 for path in train_dir.rglob("*") if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}) if train_dir.exists() else 0
    if image_count < 500:
        print(f"WARNING: only {image_count} training images found; interpret evaluation metrics cautiously.")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ML dependencies: pip install -r ml/requirements.txt") from exc
    model = YOLO(str(model_path))
    validation_options = dict(
        data=str(data_path), split=args.split, project=str(args.project.resolve()),
        name=args.name, plots=True, iou=args.iou, imgsz=args.imgsz,
    )
    metrics = model.val(**validation_options)
    box = metrics.box
    operating_point = None
    if args.confidence is not None:
        from ml.calibrate import locate_split, read_ground_truth, score_threshold

        image_dir, labels_dir = locate_split(data, data_path, args.split)
        image_suffixes = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
        images = sorted(path for path in image_dir.rglob("*") if path.suffix.lower() in image_suffixes)
        predictions = model.predict(
            source=[str(path) for path in images], imgsz=args.imgsz, conf=0.001,
            iou=args.iou, verbose=False,
        )
        if len(predictions) != len(images):
            raise SystemExit(f"Expected {len(images)} predictions, received {len(predictions)}")
        per_image = []
        for image_path, result in zip(images, predictions):
            height, width = result.orig_shape
            label_path = labels_dir / image_path.relative_to(image_dir).with_suffix(".txt")
            ground_truth = read_ground_truth(label_path, width, height)
            boxes = result.boxes
            predicted_boxes = boxes.xyxy.cpu().tolist() if boxes is not None else []
            scores = boxes.conf.cpu().tolist() if boxes is not None else []
            per_image.append((ground_truth, predicted_boxes, scores))
        operating_point = score_threshold(per_image, args.confidence, match_iou=0.5)
    summary = {
        "split": args.split,
        "confidence_threshold": args.confidence,
        "nms_iou": args.iou,
        "images_in_train": image_count,
        "precision": operating_point["precision"] if operating_point else float(box.mp),
        "recall": operating_point["recall"] if operating_point else float(box.mr),
        "map50": float(box.map50),
        "map50_95": float(box.map),
        "per_class": {},
        "confusion_matrix": str((args.project.resolve() / args.name / "confusion_matrix.png").resolve()),
    }
    if operating_point:
        summary["operating_point"] = operating_point
    for index, class_id in enumerate(box.ap_class_index):
        name = names[int(class_id)] if int(class_id) < len(names) else str(class_id)
        summary["per_class"][name] = {
            "precision": operating_point["precision"] if operating_point and int(class_id) == 0 else float(box.p[index]),
            "recall": operating_point["recall"] if operating_point and int(class_id) == 0 else float(box.r[index]),
            "map50": float(box.ap50[index]), "map50_95": float(box.ap[index]),
        }
    print(json.dumps(summary, indent=2))
    output = args.project.resolve() / args.name / "metrics.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Metrics saved to {output.resolve()}")


if __name__ == "__main__":
    main()

