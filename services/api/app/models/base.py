"""
SQLAlchemy declarative base and shared mixins.
All models inherit from Base and use UUIDs as primary keys.

GUID and JSONType use dialect-aware implementations:
  - PostgreSQL: native UUID and JSONB
  - SQLite (tests): String and JSON fallbacks
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func, types
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ── Dialect-agnostic GUID type ────────────────────────────────────────────────

class GUID(types.TypeDecorator):
    """
    Platform-independent UUID type.
    Uses PostgreSQL's native UUID; falls back to String(36) on SQLite.
    """

    impl = types.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(types.String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


# ── Dialect-agnostic JSON type ────────────────────────────────────────────────

class JSONType(types.TypeDecorator):
    """
    Platform-independent JSON type.
    Uses PostgreSQL's JSONB; falls back to standard JSON on SQLite.
    """

    impl = types.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(types.JSON())


# ── Base and mixins ───────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class UUIDMixin:
    """Provides a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    """Provides created_at / updated_at audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
