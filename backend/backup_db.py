from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

from app.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent online SQLite backup.")
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    source_path = get_settings().database_path
    destination = args.destination.expanduser().resolve()
    if not source_path.is_file():
        raise SystemExit(f"Database file does not exist: {source_path}")
    if destination == source_path:
        raise SystemExit("Backup destination must differ from the active database file")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_path) as source, sqlite3.connect(destination) as target:
        source.backup(target)
    print(f"Consistent SQLite backup written to {destination}")


if __name__ == "__main__":
    main()

