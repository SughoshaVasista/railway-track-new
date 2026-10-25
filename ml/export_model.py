from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Export trained YOLO weights for server and edge inference.")
    parser.add_argument("--model", type=Path, default=Path("runs/detect/railway-crack-yolov8s-precision/weights/best.pt"))
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--formats", nargs="+", choices=("onnx", "litert", "tflite"), default=("onnx", "litert"))
    args = parser.parse_args()
    model_path = args.model.resolve()
    if not model_path.is_file():
        raise SystemExit(f"Model checkpoint not found: {model_path}")
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("Install ML dependencies: pip install -r ml/requirements.txt") from exc
    model = YOLO(str(model_path))
    for model_format in args.formats:
        export_format = "litert" if model_format == "tflite" else model_format
        try:
            result = model.export(format=export_format, imgsz=args.imgsz)
            print(f"Exported {model_format} (.tflite for LiteRT): {result}")
        except Exception as exc:
            raise SystemExit(
                f"{model_format} export failed: {exc}. See the Ultralytics export docs for platform-specific dependencies."
            ) from exc


if __name__ == "__main__":
    main()

