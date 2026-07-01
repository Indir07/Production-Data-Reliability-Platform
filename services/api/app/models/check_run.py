import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import GUID, Base, JSONType, UUIDMixin


class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class TriggeredBy(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
    WEBHOOK = "WEBHOOK"
    CI = "CI"


class CheckRun(Base, UUIDMixin):
    """
    A single execution of a CheckDefinition.

    This table is converted to a TimescaleDB hypertable on `started_at`
    for efficient time-series queries (see Alembic migration).

    result_payload stores the full CheckResult.to_dict() output from
    the check engine, including metric_value, threshold, and details.
    """

    __tablename__ = "check_runs"

    check_definition_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("check_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"),
        nullable=False,
        default=RunStatus.RUNNING,
        index=True,
    )
    triggered_by: Mapped[TriggeredBy] = mapped_column(
        Enum(TriggeredBy, name="triggered_by"),
        nullable=False,
        default=TriggeredBy.MANUAL,
    )

    # Timing — started_at is the hypertable partition column
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Result payload from the check engine (CheckResult.to_dict())
    result_payload: Mapped[dict | None] = mapped_column(JSONType(), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    check_definition: Mapped["CheckDefinition"] = relationship(back_populates="runs")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<CheckRun id={self.id} status={self.status} "
            f"check={self.check_definition_id} started={self.started_at}>"
        )
