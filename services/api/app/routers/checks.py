import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.check_definition import CheckDefinition, CheckType
from app.models.check_run import CheckRun
from app.schemas.check import (
    CheckDefinitionCreate,
    CheckDefinitionListResponse,
    CheckDefinitionResponse,
    CheckDefinitionUpdate,
    CheckRunListResponse,
    CheckRunResponse,
    TriggerRunRequest,
)
from app.services.check_execution import CheckExecutionService

router = APIRouter()
logger = structlog.get_logger()
_execution_service = CheckExecutionService()


@router.post(
    "/checks",
    response_model=CheckDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a check definition",
)
async def create_check(
    payload: CheckDefinitionCreate,
    db: AsyncSession = Depends(get_db),
) -> CheckDefinitionResponse:
    """Create a new data quality check definition."""
    check = CheckDefinition(**payload.model_dump())
    db.add(check)
    await db.flush()
    logger.info("check_created", id=str(check.id), name=check.name, type=check.check_type)
    return CheckDefinitionResponse.model_validate(check)


@router.get(
    "/checks",
    response_model=CheckDefinitionListResponse,
    summary="List check definitions",
)
async def list_checks(
    org_id: str = Query("default"),
    check_type: CheckType | None = Query(None),
    datasource_id: uuid.UUID | None = Query(None),
    enabled_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CheckDefinitionListResponse:
    """List check definitions with optional filters."""
    q = select(CheckDefinition).where(CheckDefinition.org_id == org_id)
    if check_type:
        q = q.where(CheckDefinition.check_type == check_type)
    if datasource_id:
        q = q.where(CheckDefinition.datasource_id == datasource_id)
    if enabled_only:
        q = q.where(CheckDefinition.enabled == True)  # noqa: E712

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    items_result = await db.execute(
        q.order_by(CheckDefinition.created_at.desc()).limit(limit).offset(offset)
    )
    items = items_result.scalars().all()

    return CheckDefinitionListResponse(
        items=[CheckDefinitionResponse.model_validate(c) for c in items],
        total=total,
    )


@router.get(
    "/checks/{check_id}",
    response_model=CheckDefinitionResponse,
    summary="Get a check definition by ID",
)
async def get_check(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> CheckDefinitionResponse:
    result = await db.execute(select(CheckDefinition).where(CheckDefinition.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")
    return CheckDefinitionResponse.model_validate(check)


@router.patch(
    "/checks/{check_id}",
    response_model=CheckDefinitionResponse,
    summary="Update a check definition",
)
async def update_check(
    check_id: uuid.UUID,
    payload: CheckDefinitionUpdate,
    db: AsyncSession = Depends(get_db),
) -> CheckDefinitionResponse:
    result = await db.execute(select(CheckDefinition).where(CheckDefinition.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(check, field, value)

    await db.flush()
    await db.refresh(check)
    return CheckDefinitionResponse.model_validate(check)


@router.delete(
    "/checks/{check_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a check definition",
)
async def delete_check(
    check_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(CheckDefinition).where(CheckDefinition.id == check_id))
    check = result.scalar_one_or_none()
    if not check:
        raise HTTPException(status_code=404, detail="CheckDefinition not found")
    await db.delete(check)
    logger.info("check_deleted", id=str(check_id))


@router.post(
    "/checks/{check_id}/run",
    response_model=CheckRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger a manual check run",
)
async def trigger_run(
    check_id: uuid.UUID,
    payload: TriggerRunRequest = TriggerRunRequest(),
    db: AsyncSession = Depends(get_db),
) -> CheckRunResponse:
    """
    Immediately execute a check and return the result.
    Sprint 2: synchronous execution.
    Sprint 3: dispatches to Celery worker, returns run ID for polling.
    """
    try:
        run = await _execution_service.execute(
            check_definition_id=check_id,
            triggered_by=payload.triggered_by,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return CheckRunResponse.model_validate(run)


@router.get(
    "/checks/{check_id}/runs",
    response_model=CheckRunListResponse,
    summary="Get run history for a check",
)
async def list_runs_for_check(
    check_id: uuid.UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> CheckRunListResponse:
    """Returns the most recent check runs, newest first."""
    q = select(CheckRun).where(CheckRun.check_definition_id == check_id)
    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    items_result = await db.execute(
        q.order_by(CheckRun.started_at.desc()).limit(limit).offset(offset)
    )
    runs = items_result.scalars().all()

    return CheckRunListResponse(
        items=[CheckRunResponse.model_validate(r) for r in runs],
        total=total,
    )
