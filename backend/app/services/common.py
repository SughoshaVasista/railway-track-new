from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.database import utc_now


class ServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12].upper()}"


def timestamp_value(value: datetime | str | None) -> str:
    if value is None:
        return utc_now()
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def row_dict(row: Any) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def priority_for_severity(severity: str) -> str:
    return {"S1": "LOW", "S2": "MEDIUM", "S3": "CRITICAL"}[severity]

