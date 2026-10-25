from dataclasses import dataclass
from typing import Any


@dataclass
class AppError(Exception):
    status_code: int
    code: str
    message: str
    details: Any = None
