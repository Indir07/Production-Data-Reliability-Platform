"""
Schema Drift Detection
======================
Captures a snapshot of a table's schema and compares it to the last
known snapshot. Flags additions, removals, and type changes.

Config params:
    baseline_schema (list[dict]): The known-good schema snapshot.
        Each entry: {"column_name": str, "data_type": str, "is_nullable": bool}
    ignore_columns  (list[str]) : Column names to exclude from comparison.
                                  Useful for audit columns (created_at, etc.)

Result metric:
    drift_count — number of schema changes detected.

What we detect:
    - Column ADDED   (new column present in DB but not in baseline)
    - Column REMOVED (column in baseline but missing from DB)
    - TYPE CHANGED   (same name, different data_type)
    - NULLABLE CHANGED (nullable constraint flipped)

Why this matters:
    A dbt model or upstream team renames a column. Your pipeline silently
    starts producing NULLs or failing with key errors. Schema drift
    detection catches this the moment the DDL changes.
"""
from __future__ import annotations

import hashlib
import json

import structlog

from app.checks.base import BaseCheck, CheckConfig, CheckResult, CheckStatus
from app.connectors.base import BaseConnector

logger = structlog.get_logger()


def _schema_hash(columns: list[dict]) -> str:
    """Deterministic hash of a schema for quick equality checks."""
    canonical = json.dumps(
        sorted(columns, key=lambda c: c["column_name"]),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def _diff_schemas(
    baseline: list[dict],
    current: list[dict],
    ignore_columns: list[str],
) -> list[dict]:
    """
    Compare baseline schema to current schema.
    Returns a list of change records.
    """
    ignore = {c.lower() for c in ignore_columns}

    baseline_map = {
        c["column_name"].lower(): c
        for c in baseline
        if c["column_name"].lower() not in ignore
    }
    current_map = {
        c["column_name"].lower(): c
        for c in current
        if c["column_name"].lower() not in ignore
    }

    changes = []

    # Removed columns
    for col_name in baseline_map:
        if col_name not in current_map:
            changes.append({
                "change_type": "COLUMN_REMOVED",
                "column": col_name,
                "baseline_type": baseline_map[col_name]["data_type"],
                "current_type": None,
            })

    # Added columns
    for col_name in current_map:
        if col_name not in baseline_map:
            changes.append({
                "change_type": "COLUMN_ADDED",
                "column": col_name,
                "baseline_type": None,
                "current_type": current_map[col_name]["data_type"],
            })

    # Type or nullability changes
    for col_name in baseline_map:
        if col_name in current_map:
            b = baseline_map[col_name]
            c = current_map[col_name]
            if b["data_type"] != c["data_type"]:
                changes.append({
                    "change_type": "TYPE_CHANGED",
                    "column": col_name,
                    "baseline_type": b["data_type"],
                    "current_type": c["data_type"],
                })
            if b.get("is_nullable") != c.get("is_nullable"):
                changes.append({
                    "change_type": "NULLABLE_CHANGED",
                    "column": col_name,
                    "baseline_nullable": b.get("is_nullable"),
                    "current_nullable": c.get("is_nullable"),
                })

    return changes


class SchemaDriftCheck(BaseCheck):
    """
    Fetches the current schema from information_schema.columns and
    compares it against the baseline snapshot stored in check config.
    """

    check_type = "schema_drift"

    # SQL to fetch current schema from PostgreSQL information_schema
    _SCHEMA_SQL = """
        SELECT
            column_name,
            data_type,
            CASE is_nullable WHEN 'YES' THEN true ELSE false END AS is_nullable
        FROM information_schema.columns
        WHERE table_name   = '{table_name}'
          AND table_schema = '{schema_name}'
        ORDER BY ordinal_position
    """

    async def _execute(
        self,
        connector: BaseConnector,
        config: CheckConfig,
    ) -> CheckResult:
        table = config.target_table
        params = config.params

        # Parse table into schema.table parts
        parts = table.split(".")
        table_name = parts[-1].strip('"')
        schema_name = parts[-2].strip('"') if len(parts) > 1 else "public"

        baseline_schema: list[dict] = params.get("baseline_schema", [])
        ignore_columns: list[str] = params.get("ignore_columns", [])

        if not baseline_schema:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=(
                    "Missing required param: baseline_schema. "
                    "Run a schema snapshot first to establish a baseline."
                ),
                metric_name="drift_count",
                metric_value=None,
                threshold=0,
            )

        sql = self._SCHEMA_SQL.format(
            table_name=table_name,
            schema_name=schema_name,
        )

        logger.info("schema_drift_check_running", table=table)

        current_schema = await connector.fetch_all(sql)

        if not current_schema:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=f"Table {table} not found in information_schema. Does it exist?",
                metric_name="drift_count",
                metric_value=None,
                threshold=0,
            )

        changes = _diff_schemas(baseline_schema, current_schema, ignore_columns)
        drift_count = len(changes)

        baseline_hash = _schema_hash(baseline_schema)
        current_hash = _schema_hash(list(current_schema))

        if drift_count > 0:
            status = CheckStatus.FAIL
            change_summary = ", ".join(
                f"{c['change_type']}({c['column']})" for c in changes
            )
            message = (
                f"Schema drift detected in {table}: "
                f"{drift_count} change(s) — {change_summary}"
            )
        else:
            status = CheckStatus.PASS
            message = f"No schema drift detected in {table}. Schema is stable."

        logger.info(
            "schema_drift_check_complete",
            table=table,
            status=status,
            drift_count=drift_count,
        )

        return CheckResult(
            status=status,
            message=message,
            metric_name="drift_count",
            metric_value=float(drift_count),
            threshold=0.0,
            details={
                "changes": changes,
                "baseline_hash": baseline_hash,
                "current_hash": current_hash,
                "current_column_count": len(current_schema),
                "baseline_column_count": len(baseline_schema),
                "ignored_columns": ignore_columns,
            },
        )
