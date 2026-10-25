from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a pretrained YOLO railway-crack detector.")
    parser.add_argument("--data", type=Path, default=Path("data/datasets/railway-crack-detection-15/data.yaml"))
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--model", default="yolov8s.pt", help="Pretrained YOLO checkpoint; use yolov8n.pt for a smaller model.")
    parser.add_argument("--device", default=None, help="Use 0 for the first CUDA GPU or cpu; auto-detected by default.")
    parser.add_argument("--project", type=Path, default=Path("runs/detect"))
    parser.add_argument("--name", default="railway-crack-yolov8s-precision")
    parser.add_argument("--patience", type=int, default=25)
    parser.add_argument("--lr0", type=float, default=0.001)
    parser.add_argument("--fraction", type=float, default=1.0, help="Fraction of training images to use, from 0 to 1.")
    parser.add_argument("--optimizer", choices=("AdamW", "SGD", "auto"), default="AdamW")
    parser.add_argument("--weight-decay", type=float, default=0.0005)
    parser.add_argument("--mosaic", type=float, default=0.4)
    parser.add_argument("--close-mosaic", type=int, default=15)
    parser.add_argument("--mixup", type=float, default=0.0)
    args = parser.parse_args()

    if not 0 < args.fraction <= 1:
        raise SystemExit("Training fraction must be in (0, 1].")

    data_path = args.data.resolve()
    if not data_path.is_file():
        raise SystemExit(f"Dataset YAML not found: {data_path}")
    data = yaml.safe_load(data_path.read_text(encoding="utf-8"))
    names = data.get("names", [])
    if isinstance(names, dict):
        names = [names[key] for key in sorted(names, key=lambda value: int(value))]
    print(f"Training on {len(names)} class(es): {names}")

    try:
        from ultralytics import YOLO
        import torch
    except ImportError as exc:
        raise SystemExit("Install ML dependencies: pip install -r ml/requirements.txt") from exc

    device = args.device or ("0" if torch.cuda.is_available() else "cpu")
    project = args.project.resolve()
    model = YOLO(args.model)
    options = dict(
        data=str(data_path), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, device=device,
        project=str(project), name=args.name, exist_ok=True, save_period=10, val=True,
        patience=args.patience, workers=2, plots=True, pretrained=True,
        optimizer=args.optimizer, lr0=args.lr0, weight_decay=args.weight_decay,
        cos_lr=True, seed=42, deterministic=True,
        fraction=args.fraction,
        mosaic=args.mosaic, close_mosaic=args.close_mosaic, mixup=args.mixup,
        hsv_h=0.015, hsv_s=0.4, hsv_v=0.25,
        degrees=3.0, translate=0.05, scale=0.3,
        fliplr=0.5, flipud=0.0,
    )
    try:
        model.train(**options)
    except torch.cuda.OutOfMemoryError:
        if device == "cpu" or args.batch <= 8:
            raise
        print("CUDA memory exhausted; clearing cache and retrying with batch=8.")
        torch.cuda.empty_cache()
        model = YOLO(args.model)
        options["batch"] = 8
        options["name"] = f"{args.name}-batch8"
        model.train(**options)

    best = project / options["name"] / "weights" / "best.pt"
    print(f"Training complete. Best checkpoint: {best}")
    print("Calibrate its confidence threshold on validation data with: ")
    print(f"  python -m ml.calibrate --model \"{best}\" --data \"{data_path}\"")


if __name__ == "__main__":
    main()
