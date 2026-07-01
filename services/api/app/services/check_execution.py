"""
Check Execution Service
=======================
Orchestrates a synchronous check run:
  1. Validates the CheckDefinition
  2. Builds a connector for the target DataSource
  3. Runs the appropriate checker
  4. Persists the CheckRun result to PostgreSQL

Sprint 3 will replace the synchronous execute() with an async Celery task.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checks.base import BaseCheck, CheckConfig, CheckSeverity
from app.checks.duplicates import DuplicateCheck
from app.checks.freshness import FreshnessCheck
from app.checks.nulls import NullCheck
from app.checks.schema_drift import SchemaDriftCheck
from app.checks.volume import VolumeCheck
from app.connectors.base import MockConnector
from app.models.check_definition import CheckDefinition, CheckType
from app.models.check_run import CheckRun, RunStatus, TriggeredBy

logger = structlog.get_logger()

# ── Checker registry ──────────────────────────────────────────────────────────
_CHECKER_MAP: dict[CheckType, BaseCheck] = {
    CheckType.FRESHNESS: FreshnessCheck(),
    CheckType.SCHEMA_DRIFT: SchemaDriftCheck(),
    CheckType.NULL_EXPLOSION: NullCheck(),
    CheckType.VOLUME_ANOMALY: VolumeCheck(),
    CheckType.DUPLICATE: DuplicateCheck(),
}


class CheckExecutionService:
    """
    Synchronously executes a check and persists the result.

    Sprint 2: Uses MockConnector (no live DB connector yet).
    Sprint 3: Dispatcher replaced by Celery task.
    Sprint 2+: PostgreSQLConnector wired to real asyncpg pool.
    """

    async def execute(
        self,
        check_definition_id: uuid.UUID,
        triggered_by: TriggeredBy,
        db: AsyncSession,
    ) -> CheckRun:
        # ── 1. Load CheckDefinition ───────────────────────────────────────────
        result = await db.execute(
            select(CheckDefinition).where(CheckDefinition.id == check_definition_id)
        )
        check_def = result.scalar_one_or_none()

        if check_def is None:
            raise ValueError(f"CheckDefinition {check_definition_id} not found")

        if not check_def.enabled:
            raise ValueError(f"CheckDefinition {check_definition_id} is disabled")

        # ── 2. Create CheckRun record (status=RUNNING) ────────────────────────
        run = CheckRun(
            check_definition_id=check_def.id,
            status=RunStatus.RUNNING,
            triggered_by=triggered_by,
            started_at=datetime.now(UTC),
        )
        db.add(run)
        await db.flush()  # get the ID without committing

        logger.info(
            "check_run_started",
            run_id=str(run.id),
            check_id=str(check_def.id),
            check_type=check_def.check_type,
            table=check_def.target_table,
        )

        try:
            # ── 3. Get the right checker ──────────────────────────────────────
            checker = _CHECKER_MAP.get(check_def.check_type)
            if checker is None:
                raise ValueError(f"No checker registered for type: {check_def.check_type}")

            # ── 4. Build connector ────────────────────────────────────────────
            # Sprint 2: MockConnector — real connectors wired in Sprint 2b/3
            # when PostgreSQLConnector gets an asyncpg pool from the DataSource config.
            connector = MockConnector()
            # TODO Sprint 3: connector = await build_connector(check_def.datasource)

            # ── 5. Build check config ─────────────────────────────────────────
            config = CheckConfig(
                check_id=str(check_def.id),
                datasource_id=str(check_def.datasource_id),
                target_table=check_def.target_table,
                severity=CheckSeverity[check_def.severity.value],
                params=check_def.params,
            )

            # ── 6. Execute ────────────────────────────────────────────────────
            check_result = await checker.run(connector, config)

            # ── 7. Map result to CheckRun ─────────────────────────────────────
            run.status = RunStatus[check_result.status.value]
            run.result_payload = check_result.to_dict()
            run.duration_ms = check_result.duration_ms

        except Exception as exc:
            logger.error(
                "check_run_failed",
                run_id=str(run.id),
                error=str(exc),
            )
            run.status = RunStatus.ERROR
            run.error_message = str(exc)

        finally:
            run.completed_at = datetime.now(UTC)

        await db.flush()

        logger.info(
            "check_run_completed",
            run_id=str(run.id),
            status=run.status,
            duration_ms=run.duration_ms,
        )

        return run
