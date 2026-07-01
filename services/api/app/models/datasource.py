import enum

from sqlalchemy import Boolean, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, UUIDMixin


class DataSourceType(str, enum.Enum):
    POSTGRESQL = "postgresql"
    BIGQUERY = "bigquery"
    SNOWFLAKE = "snowflake"
    DELTA_LAKE = "delta_lake"
    REDSHIFT = "redshift"
    MYSQL = "mysql"
    SQLITE = "sqlite"


class DataSource(Base, UUIDMixin, TimestampMixin):
    """
    Represents a monitored data source (e.g. a PostgreSQL database).

    connection_config stores encrypted connection details as JSON.
    Encryption is handled at the application layer (Sprint 7).
    """

    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[DataSourceType] = mapped_column(
        Enum(DataSourceType, name="datasource_type"),
        nullable=False,
    )
    # Stored as JSON — will be encrypted in Sprint 7
    # Example: {"host": "...", "port": 5432, "database": "...", "user": "...", "password": "..."}
    connection_config: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    org_id: Mapped[str] = mapped_column(String(100), default="default", nullable=False, index=True)

    # Relationships
    check_definitions: Mapped[list["CheckDefinition"]] = relationship(  # noqa: F821
        back_populates="datasource",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<DataSource id={self.id} name={self.name} type={self.source_type}>"
