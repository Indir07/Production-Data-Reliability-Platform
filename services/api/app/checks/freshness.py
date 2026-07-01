"""
Freshness Check
===============
Verifies that a table has been updated within a configurable time window.

Config params:
    timestamp_column (str)  : Column containing the last update time.
                              Must be a TIMESTAMP / TIMESTAMPTZ column.
    max_age_hours    (float): Maximum acceptable age in hours. Default: 24.
    use_count        (bool) : If True, also check that row count > 0.

Result metric:
    age_hours — hours since the most recent row was written.

Example config:
    {
        "timestamp_column": "updated_at",
        "max_age_hours": 6.0
    }

Why this matters:
    A table that hasn't been updated in 6h when it should update hourly
    is a silent pipeline failure. Without freshness monitoring, analysts
    continue trusting stale data.
"""
from __future__ import annotations

import structlog

from app.checks.base import (
    BaseCheck,
    CheckConfig,
    CheckResult,
    CheckStatus,
    validate_sql_identifier,
)
from app.connectors.base import BaseConnector

logger = structlog.get_logger()


class FreshnessCheck(BaseCheck):
    """
    Checks that MAX(timestamp_column) is within max_age_hours of NOW().

    Supports any SQL dialect that has a NOW() / CURRENT_TIMESTAMP function
    and EXTRACT(EPOCH FROM ...) or equivalent age computation.
    """

    check_type = "freshness"

    async def _execute(
        self,
        connector: BaseConnector,
        config: CheckConfig,
    ) -> CheckResult:
        table = config.target_table
        params = config.params

        timestamp_col = params.get("timestamp_column")
        if not timestamp_col:
            return CheckResult(
                status=CheckStatus.ERROR,
                message="Missing required param: timestamp_column",
                metric_name="age_hours",
                metric_value=None,
                threshold=None,
            )

        max_age_hours: float = float(params.get("max_age_hours", 24.0))
        use_count: bool = bool(params.get("use_count", True))

        # Validate column name — prevents SQL injection via user-supplied params
        # (table name is already validated in CheckConfig.__post_init__)
        try:
            timestamp_col = validate_sql_identifier(timestamp_col, "timestamp_column")
        except ValueError as e:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=str(e),
                metric_name="age_hours",
                metric_value=None,
                threshold=None,
            )

        # ── Build SQL ─────────────────────────────────────────────────────────
        # EXTRACT(EPOCH FROM ...) works in PostgreSQL.
        # BigQuery equivalent: TIMESTAMP_DIFF(CURRENT_TIMESTAMP(), MAX(...), HOUR)
        # We'll abstract dialect differences in Sprint 2's connector layer.
        sql = f"""  # nosec B608 - table/col validated by validate_sql_identifier()
            SELECT
                MAX({timestamp_col})                         AS last_updated_at,
                EXTRACT(EPOCH FROM (NOW() - MAX({timestamp_col}))) / 3600.0
                                                             AS age_hours,
                COUNT(*)                                     AS row_count
            FROM {table}
        """

        logger.info(
            "freshness_check_running",
            table=table,
            timestamp_col=timestamp_col,
            max_age_hours=max_age_hours,
        )

        row = await connector.fetch_one(sql)

        if row is None:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=f"No result returned when querying {table}",
                metric_name="age_hours",
                metric_value=None,
                threshold=max_age_hours,
            )

        age_hours: float | None = row.get("age_hours")
        row_count: int = int(row.get("row_count", 0))
        last_updated_at = row.get("last_updated_at")

        # ── Empty table check ─────────────────────────────────────────────────
        if use_count and row_count == 0:
            return CheckResult(
                status=CheckStatus.FAIL,
                message=f"Table {table} is empty (0 rows). Expected data.",
                metric_name="age_hours",
                metric_value=None,
                threshold=max_age_hours,
                details={"row_count": 0, "last_updated_at": None},
            )

        # ── NULL max timestamp (table has rows but no timestamp data) ─────────
        if age_hours is None:
            return CheckResult(
                status=CheckStatus.FAIL,
                message=(
                    f"Column {timestamp_col} has no non-null values in {table}. "
                    "Cannot determine freshness."
                ),
                metric_name="age_hours",
                metric_value=None,
                threshold=max_age_hours,
                details={"row_count": row_count, "last_updated_at": None},
            )

        age_hours = round(float(age_hours), 4)

        # ── Freshness evaluation ──────────────────────────────────────────────
        if age_hours > max_age_hours:
            status = CheckStatus.FAIL
            message = (
                f"Table {table} is STALE. "
                f"Last update: {age_hours:.2f}h ago "
                f"(threshold: {max_age_hours}h)."
            )
        else:
            status = CheckStatus.PASS
            message = (
                f"Table {table} is FRESH. "
                f"Last update: {age_hours:.2f}h ago "
                f"(threshold: {max_age_hours}h)."
            )

        logger.info(
            "freshness_check_complete",
            table=table,
            status=status,
            age_hours=age_hours,
            threshold=max_age_hours,
        )

        return CheckResult(
            status=status,
            message=message,
            metric_name="age_hours",
            metric_value=age_hours,
            threshold=max_age_hours,
            details={
                "last_updated_at": str(last_updated_at) if last_updated_at else None,
                "row_count": row_count,
                "timestamp_column": timestamp_col,
            },
        )
