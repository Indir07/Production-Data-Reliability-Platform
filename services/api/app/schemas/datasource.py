import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.datasource import DataSourceType

# ── Request schemas ───────────────────────────────────────────────────────────

class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["prod-postgres"])
    description: str | None = Field(None, examples=["Production PostgreSQL database"])
    source_type: DataSourceType = Field(..., examples=[DataSourceType.POSTGRESQL])
    connection_config: dict = Field(
        ...,
        examples=[{"host": "localhost", "port": 5432, "database": "mydb", "user": "reader"}],
    )
    enabled: bool = Field(True)
    org_id: str = Field("default", max_length=100)


class DataSourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    connection_config: dict | None = None
    enabled: bool | None = None


# ── Response schemas ──────────────────────────────────────────────────────────

class DataSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    source_type: DataSourceType
    enabled: bool
    org_id: str
    created_at: datetime
    updated_at: datetime
    # NOTE: connection_config intentionally excluded from responses (security)


class DataSourceListResponse(BaseModel):
    items: list[DataSourceResponse]
    total: int
