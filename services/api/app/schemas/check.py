import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.check_definition import CheckSeverity, CheckType
from app.models.check_run import RunStatus, TriggeredBy

# ── Check Definition schemas ──────────────────────────────────────────────────

class CheckDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["orders-freshness"])
    description: str | None = None
    check_type: CheckType = Field(..., examples=[CheckType.FRESHNESS])
    severity: CheckSeverity = Field(CheckSeverity.HIGH)
    datasource_id: uuid.UUID
    target_table: str = Field(..., examples=["public.orders"])
    target_column: str | None = Field(None, examples=["customer_id"])
    params: dict = Field(
        ...,
        examples=[{"timestamp_column": "updated_at", "max_age_hours": 6}],
    )
    schedule_cron: str | None = Field(
        None,
        examples=["0 * * * *"],
        description="Cron expression for automatic scheduling. Null = manual only.",
    )
    enabled: bool = True
    org_id: str = Field("default", max_length=100)


class CheckDefinitionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    severity: CheckSeverity | None = None
    params: dict | None = None
    schedule_cron: str | None = None
    enabled: bool | None = None


class CheckDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    check_type: CheckType
    severity: CheckSeverity
    datasource_id: uuid.UUID
    target_table: str
    target_column: str | None
    params: dict
    schedule_cron: str | None
    enabled: bool
    org_id: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class CheckDefinitionListResponse(BaseModel):
    items: list[CheckDefinitionResponse]
    total: int


# ── Check Run schemas ─────────────────────────────────────────────────────────

class TriggerRunRequest(BaseModel):
    triggered_by: TriggeredBy = Field(TriggeredBy.MANUAL)


class CheckRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    check_definition_id: uuid.UUID
    status: RunStatus
    triggered_by: TriggeredBy
    started_at: datetime
    completed_at: datetime | None
    duration_ms: float | None
    result_payload: dict | None
    error_message: str | None


class CheckRunListResponse(BaseModel):
    items: list[CheckRunResponse]
    total: int
