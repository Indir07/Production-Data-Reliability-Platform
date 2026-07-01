"""
Duplicate Detection
===================
Detects duplicate records based on one or more primary key columns.

Config params:
    primary_key_columns (list[str]): Columns that together form the PK.
                                     Required.
    max_duplicate_rate  (float)    : Max acceptable duplicate rate [0–1].
                                     Default: 0.0 (zero tolerance).
    sample_rate         (float)    : Fraction of table to sample. Default: 1.0.

Result metric:
    duplicate_rate — fraction of rows that are duplicates.

How duplicates are counted:
    duplicate_count = total_rows - COUNT(DISTINCT pk_cols)

    This counts each extra occurrence of a PK value as a duplicate.
    e.g. if order_id=42 appears 3 times: 2 duplicates counted.

Why this matters:
    Duplicate order records → double-counted revenue.
    Duplicate event records → inflated funnel metrics.
    Duplicate user records → incorrect cohort analysis.

    Deduplication is expensive to fix after the fact. Catching it at
    ingestion time is orders of magnitude cheaper.
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


class DuplicateCheck(BaseCheck):
    """
    Counts rows vs distinct PK values to measure the duplicate rate.
    Supports composite primary keys (multiple columns).
    """

    check_type = "duplicate"

    async def _execute(
        self,
        connector: BaseConnector,
        config: CheckConfig,
    ) -> CheckResult:
        table = config.target_table
        params = config.params

        pk_columns: list[str] = params.get("primary_key_columns", [])
        if not pk_columns:
            return CheckResult(
                status=CheckStatus.ERROR,
                message="Missing required param: primary_key_columns",
                metric_name="duplicate_rate",
                metric_value=None,
                threshold=None,
            )

        max_duplicate_rate: float = float(params.get("max_duplicate_rate", 0.0))
        sample_rate: float = float(params.get("sample_rate", 1.0))
        sample_rate = max(0.001, min(1.0, sample_rate))

        # Validate each PK column — prevents SQL injection via user-supplied column names
        try:
            pk_columns = [validate_sql_identifier(col, "primary_key_column") for col in pk_columns]
        except ValueError as e:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=str(e),
                metric_name="duplicate_rate",
                metric_value=None,
                threshold=None,
            )

        # ── Build DISTINCT expression for composite PKs ───────────────────────
        pk_expr = ", ".join(pk_columns)

        sample_clause = ""
        if sample_rate < 1.0:
            pct = round(sample_rate * 100, 2)
            sample_clause = f"TABLESAMPLE BERNOULLI ({pct})"

        sql = f"""  # nosec B608 - table/pk_cols validated by validate_sql_identifier()
            SELECT
                COUNT(*)                    AS total_rows,
                COUNT(DISTINCT ({pk_expr})) AS unique_rows
            FROM {table} {sample_clause}
        """

        logger.info(
            "duplicate_check_running",
            table=table,
            pk_columns=pk_columns,
            max_duplicate_rate=max_duplicate_rate,
        )

        row = await connector.fetch_one(sql)

        if row is None:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=f"No result returned when querying {table}",
                metric_name="duplicate_rate",
                metric_value=None,
                threshold=max_duplicate_rate,
            )

        total_rows = int(row.get("total_rows", 0))
        unique_rows = int(row.get("unique_rows", 0))

        if total_rows == 0:
            return CheckResult(
                status=CheckStatus.SKIPPED,
                message=f"Table {table} is empty — duplicate check skipped.",
                metric_name="duplicate_rate",
                metric_value=None,
                threshold=max_duplicate_rate,
                details={"total_rows": 0},
            )

        duplicate_count = total_rows - unique_rows
        duplicate_rate = round(duplicate_count / total_rows, 6)
        duplicate_pct = round(duplicate_rate * 100, 4)

        pk_str = ", ".join(pk_columns)

        if duplicate_rate > max_duplicate_rate:
            status = CheckStatus.FAIL
            message = (
                f"Duplicate records detected in {table}: "
                f"{duplicate_count:,} duplicates on ({pk_str}). "
                f"Duplicate rate: {duplicate_pct}% (threshold: {max_duplicate_rate * 100}%). "
                f"{total_rows:,} total rows, {unique_rows:,} unique."
            )
        else:
            status = CheckStatus.PASS
            message = (
                f"No duplicates detected in {table} on ({pk_str}). "
                f"{total_rows:,} rows, all unique."
                if duplicate_count == 0
                else (
                    f"Duplicate rate acceptable in {table}: "
                    f"{duplicate_pct}% (threshold: {max_duplicate_rate * 100}%)."
                )
            )

        logger.info(
            "duplicate_check_complete",
            table=table,
            status=status,
            duplicate_rate=duplicate_rate,
            duplicate_count=duplicate_count,
            total_rows=total_rows,
        )

        return CheckResult(
            status=status,
            message=message,
            metric_name="duplicate_rate",
            metric_value=duplicate_rate,
            threshold=max_duplicate_rate,
            details={
                "primary_key_columns": pk_columns,
                "total_rows": total_rows,
                "unique_rows": unique_rows,
                "duplicate_count": duplicate_count,
                "duplicate_pct": duplicate_pct,
                "sample_rate": sample_rate,
                "sampled": sample_rate < 1.0,
            },
        )
