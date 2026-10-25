from __future__ import annotations

import argparse
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


def normalize_yaml(data_yaml: Path) -> None:
    data = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    root = data_yaml.parent.resolve()
    split_aliases = {"train": ("train",), "val": ("valid", "val"), "test": ("test",)}
    for key, directory_names in split_aliases.items():
        if key not in data:
            continue
        candidates = [root / dirname / "images" for dirname in directory_names]
        original = Path(str(data[key]))
        candidates.extend((root / original, (root / original).resolve()))
        image_dir = next((path for path in candidates if path.is_dir()), None)
        if image_dir:
            split_dir = image_dir.parent
            data[key] = f"{split_dir.name}/images"
    data["path"] = str(root)
    data_yaml.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the Roboflow railway-crack dataset in YOLOv8 format.")
    parser.add_argument("--version", type=int, default=int(os.getenv("ROBOFLOW_VERSION", "15")))
    parser.add_argument("--destination", type=Path, default=None)
    args = parser.parse_args()
    api_key = os.getenv("ROBOFLOW_API_KEY")
    if not api_key:
        raise SystemExit("Set ROBOFLOW_API_KEY in your environment before downloading the dataset.")
    destination = args.destination or Path("data/datasets") / f"railway-crack-detection-{args.version}"
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        from roboflow import Roboflow
    except ImportError as exc:
        raise SystemExit("Install ML dependencies first: pip install -r ml/requirements.txt") from exc
    workspace = os.getenv("ROBOFLOW_WORKSPACE", "thesis-group")
    project_slug = os.getenv("ROBOFLOW_PROJECT", "railway-crack-detection")
    client = Roboflow(api_key=api_key)
    project = client.workspace(workspace).project(project_slug)
    project.version(args.version).download("yolov8", location=str(destination))
    data_yaml = destination / "data.yaml"
    if not data_yaml.is_file():
        raise SystemExit(f"Roboflow export did not contain data.yaml: {destination}")
    normalize_yaml(data_yaml)
    print(f"Dataset downloaded to {destination}")
    print(f"Dataset config: {data_yaml}")
    downloaded = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    class_names = downloaded.get("names", [])
    if isinstance(class_names, dict):
        class_names = [class_names[key] for key in sorted(class_names, key=lambda value: int(value))]
    print(f"Review the downloaded class names: {class_names}")


if __name__ == "__main__":
    main()

