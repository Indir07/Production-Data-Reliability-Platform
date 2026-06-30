"""
Volume Anomaly Detection
========================
Detects abnormal row count changes using z-score statistical analysis.

Algorithm:
    z_score = (current_count - baseline_mean) / baseline_stddev

    If |z_score| > z_threshold → FAIL (anomaly detected)

    This flags both unexpected drops (data loss) and spikes (duplication
    or runaway ingestion) relative to a historical baseline.

Config params:
    baseline_mean   (float): Historical mean row count. Required.
    baseline_stddev (float): Historical std deviation of row count. Required.
    z_threshold     (float): Z-score threshold for anomaly. Default: 3.0.
                             3.0 → flags deviations beyond 3 standard deviations.
                             Lower = more sensitive. Higher = fewer alerts.
    min_row_count   (int)  : Minimum expected rows. Fails immediately if
                             current count < this value. Default: 1.

Result metric:
    z_score — number of standard deviations from the baseline mean.

Why z-score over a simple % threshold?
    A fixed threshold (e.g. "fail if ±20%") breaks for tables that
    naturally have high variance. Z-score adapts to each table's
    historical variability — high-variance tables need larger deviations
    to trigger an alert, low-variance tables are very sensitive.

How to compute baseline_mean and baseline_stddev:
    Query 30 days of daily COUNT(*) snapshots, compute mean and stddev.
    Sprint 5 will automate this via the MetricBaseline table.
"""
from __future__ import annotations

import structlog

from app.checks.base import BaseCheck, CheckConfig, CheckResult, CheckStatus
from app.connectors.base import BaseConnector

logger = structlog.get_logger()


def _compute_z_score(value: float, mean: float, stddev: float) -> float | None:
    """
    Compute z-score. Returns None if stddev is 0 (can't divide by zero).
    When stddev == 0, all historical values were identical — we use a
    simple deviation check instead.
    """
    if stddev <= 0:
        return None
    return (value - mean) / stddev


class VolumeCheck(BaseCheck):
    """
    Row-count anomaly detection using z-score against a historical baseline.
    """

    check_type = "volume_anomaly"

    async def _execute(
        self,
        connector: BaseConnector,
        config: CheckConfig,
    ) -> CheckResult:
        table = config.target_table
        params = config.params

        baseline_mean = params.get("baseline_mean")
        baseline_stddev = params.get("baseline_stddev")

        if baseline_mean is None or baseline_stddev is None:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=(
                    "Missing required params: baseline_mean and baseline_stddev. "
                    "Run a baseline computation first (Sprint 5 automates this)."
                ),
                metric_name="z_score",
                metric_value=None,
                threshold=None,
            )

        baseline_mean = float(baseline_mean)
        baseline_stddev = float(baseline_stddev)
        z_threshold: float = float(params.get("z_threshold", 3.0))
        min_row_count: int = int(params.get("min_row_count", 1))

        # ── Count rows ────────────────────────────────────────────────────────
        sql = f"SELECT COUNT(*) AS row_count FROM {table}"  # noqa: S608

        logger.info(
            "volume_check_running",
            table=table,
            baseline_mean=baseline_mean,
            baseline_stddev=baseline_stddev,
            z_threshold=z_threshold,
        )

        row = await connector.fetch_one(sql)

        if row is None:
            return CheckResult(
                status=CheckStatus.ERROR,
                message=f"No result returned when querying {table}",
                metric_name="z_score",
                metric_value=None,
                threshold=z_threshold,
            )

        current_count = int(row.get("row_count", 0))

        # ── Hard floor check ──────────────────────────────────────────────────
        if current_count < min_row_count:
            return CheckResult(
                status=CheckStatus.FAIL,
                message=(
                    f"Volume critically low in {table}: "
                    f"{current_count:,} rows (minimum: {min_row_count:,})."
                ),
                metric_name="z_score",
                metric_value=None,
                threshold=z_threshold,
                details={
                    "current_count": current_count,
                    "min_row_count": min_row_count,
                    "baseline_mean": baseline_mean,
                    "failure_reason": "below_minimum",
                },
            )

        # ── Z-score computation ───────────────────────────────────────────────
        z_score = _compute_z_score(current_count, baseline_mean, baseline_stddev)

        # Edge case: zero stddev means table always had the same count
        if z_score is None:
            if current_count != int(baseline_mean):
                status = CheckStatus.FAIL
                message = (
                    f"Volume anomaly in {table}: count changed from expected "
                    f"{int(baseline_mean):,} to {current_count:,} "
                    "(historical stddev was 0 — no variance expected)."
                )
            else:
                status = CheckStatus.PASS
                message = f"Volume stable in {table}: {current_count:,} rows (stddev=0 baseline)."

            return CheckResult(
                status=status,
                message=message,
                metric_name="z_score",
                metric_value=None,
                threshold=z_threshold,
                details={
                    "current_count": current_count,
                    "baseline_mean": baseline_mean,
                    "baseline_stddev": baseline_stddev,
                    "note": "stddev=0, z-score undefined",
                },
            )

        z_score = round(z_score, 4)
        abs_z = abs(z_score)
        deviation_pct = round(((current_count - baseline_mean) / baseline_mean) * 100, 2)

        if abs_z > z_threshold:
            direction = "spike" if z_score > 0 else "drop"
            status = CheckStatus.FAIL
            message = (
                f"Volume {direction} detected in {table}: "
                f"{current_count:,} rows (z={z_score:+.2f}, threshold=±{z_threshold}). "
                f"Expected ~{baseline_mean:,.0f} ± {baseline_stddev:,.0f}. "
                f"Deviation: {deviation_pct:+.1f}%."
            )
        else:
            status = CheckStatus.PASS
            message = (
                f"Volume normal for {table}: "
                f"{current_count:,} rows (z={z_score:+.2f}, threshold=±{z_threshold}). "
                f"Deviation: {deviation_pct:+.1f}%."
            )

        logger.info(
            "volume_check_complete",
            table=table,
            status=status,
            current_count=current_count,
            z_score=z_score,
            threshold=z_threshold,
        )

        return CheckResult(
            status=status,
            message=message,
            metric_name="z_score",
            metric_value=z_score,
            threshold=z_threshold,
            details={
                "current_count": current_count,
                "baseline_mean": baseline_mean,
                "baseline_stddev": baseline_stddev,
                "deviation_pct": deviation_pct,
                "p_lower": round(baseline_mean - z_threshold * baseline_stddev, 0),
                "p_upper": round(baseline_mean + z_threshold * baseline_stddev, 0),
            },
        )
