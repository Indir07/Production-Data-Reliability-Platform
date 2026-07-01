import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, JSONType, TimestampMixin, UUIDMixin


class CheckType(str, enum.Enum):
    FRESHNESS = "freshness"
    SCHEMA_DRIFT = "schema_drift"
    NULL_EXPLOSION = "null_explosion"
    VOLUME_ANOMALY = "volume_anomaly"
    DUPLICATE = "duplicate"


class CheckSeverity(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class CheckDefinition(Base, UUIDMixin, TimestampMixin):
    """
    A configured data quality check on a specific table/column.

    The `params` JSONB column stores check-type-specific configuration,
    e.g. for freshness: {"timestamp_column": "updated_at", "max_age_hours": 6}
    """

    __tablename__ = "check_definitions"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    check_type: Mapped[CheckType] = mapped_column(
        Enum(CheckType, name="check_type"),
        nullable=False,
        index=True,
    )
    severity: Mapped[CheckSeverity] = mapped_column(
        Enum(CheckSeverity, name="check_severity"),
        nullable=False,
        default=CheckSeverity.HIGH,
    )

    datasource_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_table: Mapped[str] = mapped_column(String(500), nullable=False)
    target_column: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Check-type-specific configuration (validated by check engine)
    params: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)

    # Scheduling
    schedule_cron: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Cron expression e.g. '0 * * * *' (hourly). Null = manual only.",
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    org_id: Mapped[str] = mapped_column(String(100), default="default", nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(255), default="system", nullable=False)

    # Relationships
    datasource: Mapped["DataSource"] = relationship(back_populates="check_definitions")  # noqa: F821
    runs: Mapped[list["CheckRun"]] = relationship(  # noqa: F821
        back_populates="check_definition",
        cascade="all, delete-orphan",
        order_by="CheckRun.started_at.desc()",
    )

    def __repr__(self) -> str:
        return (
            f"<CheckDefinition id={self.id} name={self.name} "
            f"type={self.check_type} table={self.target_table}>"
        )
