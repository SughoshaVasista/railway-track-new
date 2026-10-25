from datetime import datetime
from enum import StrEnum

from pydantic import AliasChoices, Field, model_validator

from app.schemas.common import ApiModel


class DefectType(StrEnum):
    CRACK = "CRACK"
    RUST = "RUST"
    JOINT_GAP = "JOINT_GAP"
    MISSING_FASTENER = "MISSING_FASTENER"
    RAILWAY_GAP = "RAILWAY_GAP"


class Severity(StrEnum):
    S1 = "S1"
    S2 = "S2"
    S3 = "S3"


class AlertStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DETECTED = "DETECTED"
    VERIFIED = "VERIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    UNDER_REPAIR = "UNDER_REPAIR"
    RESOLVED = "RESOLVED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    REOPENED = "REOPENED"


class Priority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SensorType(StrEnum):
    CAMERA = "CAMERA"
    ULTRASONIC = "ULTRASONIC"
    ACCELEROMETER = "ACCELEROMETER"
    TEMPERATURE = "TEMPERATURE"
    GPS = "GPS"


class SensorStatus(StrEnum):
    ONLINE = "ONLINE"
    DELAYED = "DELAYED"
    OFFLINE = "OFFLINE"


class DeviceStatus(StrEnum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class TaskStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    WORKER = "WORKER"


class BoundingBox(ApiModel):
    x1: float = Field(ge=0, allow_inf_nan=False)
    y1: float = Field(ge=0, allow_inf_nan=False)
    x2: float = Field(gt=0, allow_inf_nan=False)
    y2: float = Field(gt=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_coordinates(self):
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("bbox x2/y2 must be greater than x1/y1")
        return self


class AlertCreate(ApiModel):
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    sensor_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    defect_type: DefectType
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    severity: Severity
    priority: Priority | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    chainage: str | None = Field(default=None, max_length=120)
    timestamp: datetime | None = None
    image_url: str | None = Field(default=None, max_length=2048)
    bbox: BoundingBox | None = None

    @model_validator(mode="after")
    def paired_coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class AlertStatusUpdate(ApiModel):
    status: AlertStatus


class AlertOut(ApiModel):
    alert_id: str
    defect_id: str
    device_id: str
    device_name: str
    device_location: str | None
    sensor_id: str | None
    sensor_type: SensorType | None
    defect_type: DefectType
    confidence: float
    severity: Severity
    priority: Priority
    status: AlertStatus
    latitude: float | None
    longitude: float | None
    chainage: str | None
    timestamp: str
    image_url: str | None
    bbox: BoundingBox | None = None
    created_at: str
    resolved_at: str | None
    id: str | None = None
    defect: str | None = None
    type: str | None = None
    track: str | None = None
    gps: dict | None = None
    image: str | None = None


class DeviceCreate(ApiModel):
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    device_name: str = Field(min_length=1, max_length=120)
    location: str | None = Field(default=None, max_length=200)


class DeviceHeartbeat(ApiModel):
    location: str | None = Field(default=None, max_length=200)
    timestamp: datetime | None = None


class DeviceOut(ApiModel):
    device_id: str
    device_name: str
    location: str | None
    status: DeviceStatus
    last_seen: str | None
    created_at: str
    id: str | None = None
    name: str | None = None
    platform: str | None = None


class SensorCreate(ApiModel):
    sensor_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    sensor_type: SensorType
    sampling_rate: float | None = Field(default=None, gt=0, allow_inf_nan=False)


class SensorOut(ApiModel):
    sensor_id: str
    device_id: str
    sensor_type: SensorType
    sampling_rate: float | None
    status: SensorStatus
    created_at: str


class SensorReadingCreate(ApiModel):
    sensor_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    value: float = Field(allow_inf_nan=False)
    axis: str | None = Field(default=None, max_length=8)
    timestamp: datetime | None = None


class SensorReadingsBatch(ApiModel):
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    readings: list[SensorReadingCreate] = Field(min_length=1, max_length=500)


class SensorReadingOut(ApiModel):
    reading_id: int
    sensor_id: str
    device_id: str
    sensor_type: SensorType
    timestamp: str
    value: float
    axis: str | None


class DeviceHealth(ApiModel):
    device: DeviceOut
    sensors: list[SensorOut]
    latest_readings: list[SensorReadingOut]


class TaskCreate(ApiModel):
    alert_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    assigned_worker_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$", validation_alias=AliasChoices("assigned_worker_id", "worker_id"))
    priority: Priority | None = None
    remarks: str | None = Field(default=None, max_length=4000)


class TaskUpdate(ApiModel):
    assigned_worker_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    priority: Priority | None = None
    completion_image: str | None = Field(default=None, max_length=2048)
    remarks: str | None = Field(default=None, max_length=4000)


class TaskStatusUpdate(ApiModel):
    status: TaskStatus
    remarks: str | None = Field(default=None, max_length=4000)
    completion_image: str | None = Field(default=None, max_length=2048)


class TaskOut(ApiModel):
    task_id: str
    alert_id: str
    assigned_worker_id: str | None
    priority: Priority
    status: TaskStatus
    assigned_at: str
    started_at: str | None
    completed_at: str | None
    completion_image: str | None
    remarks: str | None
    id: str | None = None
    worker_id: str | None = None
    defect: str | None = None
    chainage: str | None = None
    image_url: str | None = None
    before_image_url: str | None = None
    after_image_url: str | None = None


class SwitchDecisionCreate(ApiModel):
    train_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    switch_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    current_track: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    selected_track: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_-]+$", validation_alias=AliasChoices("selected_track", "target_track"))
    reason: str = Field(default="Decision submitted from the operations console.", min_length=1, max_length=2000)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    emergency_stop: bool = False
    timestamp: datetime | None = None


class SwitchDecisionOut(ApiModel):
    decision_id: str
    train_id: str | None
    switch_id: str | None
    current_track: str | None
    selected_track: str | None
    reason: str
    confidence: float | None
    emergency_stop: bool
    timestamp: str


class SwitchStatus(ApiModel):
    current_track: str | None
    last_decision: SwitchDecisionOut | None


class DashboardSummary(ApiModel):
    active_alerts: int
    critical_s3: int
    moderate_s2: int
    minor_s1: int
    pending_repairs: int
    total_devices: int
    online_devices: int
    updated_at: str
    s3_alerts: int = 0
    s2_alerts: int = 0
    s1_alerts: int = 0
    pending_tasks: int = 0


class Detection(ApiModel):
    class_name: str
    defect_type: DefectType | None
    confidence: float
    bbox: BoundingBox


class InferenceResult(ApiModel):
    image_width: int
    image_height: int
    model: str
    detections: list[Detection]

