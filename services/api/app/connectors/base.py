"""
Connector abstraction layer.

Checks never talk to databases directly — they go through a BaseConnector.
This makes checkers 100% testable without a real database.

Supported connectors (Sprint 2 will wire these to real DB pools):
  - PostgreSQLConnector
  - MockConnector (for unit tests)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Abstract database connector. All checkers depend on this interface."""

    @abstractmethod
    async def fetch_one(self, sql: str, *args: Any) -> dict[str, Any] | None:
        """Execute SQL and return the first row as a dict, or None."""
        ...

    @abstractmethod
    async def fetch_all(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        """Execute SQL and return all rows as a list of dicts."""
        ...

    @property
    @abstractmethod
    def dialect(self) -> str:
        """Return the SQL dialect: 'postgresql', 'bigquery', 'snowflake'."""
        ...


class MockConnector(BaseConnector):
    """
    In-memory connector for unit tests.

    Usage:
        connector = MockConnector()
        connector.set_result("SELECT ...", {"count": 100})
        result = await connector.fetch_one("SELECT ...")
    """

    def __init__(self) -> None:
        self._results: dict[str, Any] = {}
        self._default: Any = None

    def set_result(self, sql_fragment: str, result: Any) -> MockConnector:
        """
        Register a result for any query containing `sql_fragment`.
        Returns self for chaining.
        """
        self._results[sql_fragment] = result
        return self

    def set_default(self, result: Any) -> MockConnector:
        """Fallback result when no sql_fragment matches."""
        self._default = result
        return self

    def _match(self, sql: str) -> Any:
        for fragment, result in self._results.items():
            if fragment.lower() in sql.lower():
                return result
        return self._default

    async def fetch_one(self, sql: str, *args: Any) -> dict[str, Any] | None:
        result = self._match(sql)
        if isinstance(result, list):
            return result[0] if result else None
        return result

    async def fetch_all(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        result = self._match(sql)
        if isinstance(result, list):
            return result
        if result is not None:
            return [result]
        return []

    @property
    def dialect(self) -> str:
        return "mock"


class PostgreSQLConnector(BaseConnector):
    """
    Async PostgreSQL connector backed by asyncpg.
    Connection pool is injected at construction time.

    Sprint 2 will wire this to the SQLAlchemy async engine.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def fetch_one(self, sql: str, *args: Any) -> dict[str, Any] | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None

    async def fetch_all(self, sql: str, *args: Any) -> list[dict[str, Any]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    @property
    def dialect(self) -> str:
        return "postgresql"
