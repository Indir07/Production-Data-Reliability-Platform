"""
Base classes for the PDRP check engine.

Every check type (freshness, schema drift, nulls, volume, duplicates)
inherits from BaseCheck and returns a CheckResult.
"""
from __future__ import annotations

import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class CheckSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class CheckResult:
    """
    The canonical result object returned by every checker.
    Serialised into CheckRun.result_payload in the database.
    """
    status: CheckStatus
    message: str
    metric_name: str
    metric_value: float | None
    threshold: float | None
    details: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0

    def passed(self) -> bool:
        return self.status == CheckStatus.PASS

    def failed(self) -> bool:
        return self.status == CheckStatus.FAIL

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "message": self.message,
            "metric_name": self.metric_name,
            "metric_value": self.metric_value,
            "threshold": self.threshold,
            "details": self.details,
            "duration_ms": self.duration_ms,
        }


@dataclass
class CheckConfig:
    """
    Common configuration shared across all check types.
    Checker-specific config is passed via `params`.

    Security: target_table and any column names interpolated into SQL are
    validated against a strict allowlist regex before use. This prevents
    SQL injection even though we build queries with f-strings (necessary
    because table/column names cannot be parameterised in SQL).
    """

    check_id: str
    datasource_id: str
    target_table: str
    severity: CheckSeverity = CheckSeverity.HIGH
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_sql_identifier(self.target_table)


# ── SQL identifier validation ─────────────────────────────────────────────────
# Table and column names CANNOT be passed as SQL parameters — they must be
# interpolated. To prevent SQL injection we validate all identifiers against a
# strict allowlist: only alphanumeric characters, underscores, and a single
# dot (for schema.table notation) are permitted.
#
# This is called at CheckConfig construction time and by individual checkers
# before interpolating column names from `params`.

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
_MAX_IDENTIFIER_LEN = 256


def validate_sql_identifier(name: str, label: str = "identifier") -> str:
    """
    Validate a SQL identifier (table name, column name, schema name).

    Raises ValueError if the name contains any character outside the
    safe set: letters, digits, underscore, and dot (for schema.table).

    Returns the validated name so it can be used inline:
        col = validate_sql_identifier(params["column"], "column")
    """
    if not name or not isinstance(name, str):
        raise ValueError(f"SQL {label} must be a non-empty string, got: {name!r}")
    if len(name) > _MAX_IDENTIFIER_LEN:
        raise ValueError(
            f"SQL {label} exceeds maximum length ({_MAX_IDENTIFIER_LEN}): {name!r}"
        )
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(
            f"SQL {label} contains unsafe characters: {name!r}. "
            "Only letters, digits, underscores, and dots are allowed."
        )
    return name



class BaseCheck(ABC):
    """
    Abstract base class for all data quality checks.

    Subclasses must implement `_execute()` which receives a connector
    and the check config, and returns a CheckResult.

    The `run()` method wraps execution with timing and error handling.
    """

    check_type: str = "base"

    async def run(
        self,
        connector: BaseConnector,  # noqa: F821
        config: CheckConfig,
    ) -> CheckResult:
        """
        Execute the check and return a result.
        Wraps _execute() with timing and catches unexpected errors.
        """
        start = time.perf_counter()
        try:
            result = await self._execute(connector, config)
        except Exception as exc:
            result = CheckResult(
                status=CheckStatus.ERROR,
                message=f"Check raised an unexpected error: {exc}",
                metric_name=self.check_type,
                metric_value=None,
                threshold=None,
                details={"error_type": type(exc).__name__, "error": str(exc)},
            )
        result.duration_ms = round((time.perf_counter() - start) * 1000, 2)
        return result

    @abstractmethod
    async def _execute(
        self,
        connector: BaseConnector,  # noqa: F821
        config: CheckConfig,
    ) -> CheckResult:
        """Implement the actual check logic here."""
        ...
