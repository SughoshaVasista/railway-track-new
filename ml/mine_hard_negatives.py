from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find likely false-positive images for human review before adding railway hard negatives."
    )
    parser.add_argument("--model", type=Path, default=Path("models/best.pt"))
    parser.add_argument("--source", type=Path, required=True, help="Unlabeled image or directory of images.")
    parser.add_argument("--output", type=Path, default=Path("runs/hard-negative-review"))
    parser.add_argument("--candidate-confidence", type=float, default=0.05)
    parser.add_argument("--nms-iou", type=float, default=0.55)
    parser.add_argument("--imgsz", type=int, default=960)
    args = parser.parse_args()
    if not 0 <= args.candidate_confidence <= 1 or not 0 <= args.nms_iou <= 1:
        raise SystemExit("Confidence and NMS IoU must be in [0, 1].")

    model_path, source, output = args.model.resolve(), args.source.resolve(), args.output.resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model checkpoint not found: {model_path}")
    if not source.exists():
        raise SystemExit(f"Source image/folder not found: {source}")
    images = [source] if source.is_file() else sorted(
        path for path in source.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not images:
        raise SystemExit(f"No supported images found in {source}")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ML dependencies: pip install -r ml/requirements.txt") from exc

    candidates_dir, previews_dir = output / "candidates", output / "previews"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    previews_dir.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(model_path))
    results = model.predict(
        source=[str(path) for path in images], imgsz=args.imgsz,
        conf=args.candidate_confidence, iou=args.nms_iou, verbose=False, stream=True,
    )
    report_path = output / "candidates.csv"
    with report_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["source_image", "review_copy", "preview", "detection_count", "max_confidence"])
        count = 0
        processed = 0
        for image_path, result in zip(images, results):
            processed += 1
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue
            count += 1
            review_path = candidates_dir / f"{count:05d}_{image_path.name}"
            preview_path = previews_dir / f"{count:05d}_{image_path.stem}.jpg"
            shutil.copy2(image_path, review_path)
            result.save(filename=str(preview_path))
            max_confidence = float(boxes.conf.max().item())
            writer.writerow([str(image_path), str(review_path), str(preview_path), len(boxes), max_confidence])
    if processed != len(images):
        raise SystemExit(f"Expected {len(images)} predictions, received {processed}")
    print(f"Reviewed-candidate images: {count} / {len(images)}")
    print(f"Candidate list: {report_path}")
    print("Review every image before labeling. Add only confirmed background images as negatives;")
    print("if a real crack is present, annotate it instead of creating an empty label.")


if __name__ == "__main__":
    main()
