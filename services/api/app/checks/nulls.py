"""
Null Explosion Detection
========================
Detects when the null rate of a column exceeds an acceptable threshold.

"Null explosion" = a pipeline bug silently starts writing NULLs instead
of real values. The table grows normally but data is missing.

Config params:
    column          (str)  : Column to check for nulls.
    max_null_rate   (float): Maximum acceptable null rate [0.0 – 1.0].
                             Default: 0.05 (5%).
    sample_rate     (float): Fraction of table to sample [0.0 – 1.0].
                             Default: 1.0 (full scan). Use 0.1 for
                             large tables to run in < 5s.

Result metric:
    null_rate — fraction of rows where column IS NULL.

Why this matters:
    An upstream ETL starts producing nulls for `customer_id`. Revenue
    reports still show correct totals but attribution breaks completely.
    Analysts trust the data for 3 days before someone notices.
"""
from __future__ import annotations

import structlog

from app.checks.base import BaseCheck, CheckConfig, CheckResult, CheckStatus
from app.connectors.base import BaseConnector

logger = structlog.get_logger()


class NullCheck(BaseCheck):
    """
    Computes the null rate for a specific column.
    Optionally uses TABLESAMPLE for large tables.
    """

    check_type = "null_explosion"

    async def _execute(
        self,
        connector: BaseConnector,
        config: CheckConfig,
    ) -> CheckResult:
        table = config.target_table
        params = config.params

        column = params.get("column")
        if not column:
            return CheckResult(
                status=CheckStatus.ERROR,
                message="Missing required param: column",
                metric_name="null_rate",
                metric_value=None,
                threshold=None,
            )

        max_null_rate: float = float(params.get("max_null_rate", 0.05))
        sample_rate: float = float(params.get("sample_rate", 1.0))
        sample_rate = max(0.001, min(1.0, sample_rate))  # clamp to [0.001, 1.0]

        # ── Build sampling clause ─────────────────────────────────────────────
        # TABLESAMPLE BERNOULLI(pct) is ANSI SQL and supported by PostgreSQL,
        # BigQuery, Snowflake, and Redshift.
        sample_clause = ""
        if sample_rate < 1.0:
            pct = round(sample_rate * 100, 2)
            sample_clause = f"TABLESAMPLE BERNOULLI ({pct})"

        sql = f"""
            SELECT
                COUNT(*)                  AS total_rows,
                COUNT({column})           AS non_null_rows,
                COUNT(*) - COUNT({column}) AS null_rows
            FROM {table} {sample_clause}
        """  # noqa: S608

        logger.info(
            "null_check_running",
            table=table,
            column=column,
            max_null_rate=max_null_rate,
            sample_rate=sample_rate,
        )

        row = await connector.fetch_one(sql)

        if row is None:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=f"No result returned when querying {table}",
                metric_name="null_rate",
                metric_value=None,
                threshold=max_null_rate,
            )

        total_rows = int(row.get("total_rows", 0))
        null_rows = int(row.get("null_rows", 0))

        if total_rows == 0:
            return CheckResult(
                status=CheckStatus.SKIPPED,
                message=f"Table {table} is empty — null check skipped.",
                metric_name="null_rate",
                metric_value=None,
                threshold=max_null_rate,
                details={"total_rows": 0},
            )

        null_rate = round(null_rows / total_rows, 6)
        null_pct = round(null_rate * 100, 2)

        if null_rate > max_null_rate:
            status = CheckStatus.FAIL
            message = (
                f"Null explosion detected in {table}.{column}: "
                f"{null_pct}% null (threshold: {max_null_rate * 100}%). "
                f"{null_rows:,} of {total_rows:,} rows are NULL."
            )
        else:
            status = CheckStatus.PASS
            message = (
                f"Null rate acceptable for {table}.{column}: "
                f"{null_pct}% null (threshold: {max_null_rate * 100}%)."
            )

        logger.info(
            "null_check_complete",
            table=table,
            column=column,
            status=status,
            null_rate=null_rate,
            threshold=max_null_rate,
        )

        return CheckResult(
            status=status,
            message=message,
            metric_name="null_rate",
            metric_value=null_rate,
            threshold=max_null_rate,
            details={
                "column": column,
                "total_rows": total_rows,
                "null_rows": null_rows,
                "non_null_rows": total_rows - null_rows,
                "null_pct": null_pct,
                "sample_rate": sample_rate,
                "sampled": sample_rate < 1.0,
            },
        )
