from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ActionNotes(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)


class AssignAlertRequest(ActionNotes):
    worker_id: str = Field(min_length=1, max_length=64)


class AlertPriorityRequest(BaseModel):
    severity: Literal["S1", "S2", "S3"]


class CreateTaskRequest(BaseModel):
    alert_id: str = Field(min_length=1, max_length=64)
    worker_id: str = Field(min_length=1, max_length=64)
    status: Literal["ASSIGNED"] = "ASSIGNED"
    notes: str | None = Field(default=None, max_length=4000)


class TaskStatusRequest(BaseModel):
    status: Literal["ACCEPTED", "IN_PROGRESS", "COMPLETED"]
    notes: str | None = Field(default=None, max_length=4000)


class TaskReviewRequest(BaseModel):
    decision: Literal["approve", "request_changes"]
    notes: str | None = Field(default=None, max_length=4000)


class EvidenceMetadata(BaseModel):
    notes: str | None = None
    evidence_type: Literal["before", "after", "repair", "other"] = "repair"
