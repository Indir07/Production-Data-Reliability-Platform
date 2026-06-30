"""
Base classes for the PDRP check engine.

Every check type (freshness, schema drift, nulls, volume, duplicates)
inherits from BaseCheck and returns a CheckResult.
"""
from __future__ import annotations

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
    """
    check_id: str
    datasource_id: str
    target_table: str
    severity: CheckSeverity = CheckSeverity.HIGH
    params: dict[str, Any] = field(default_factory=dict)


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
