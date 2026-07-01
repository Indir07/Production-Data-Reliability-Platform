import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.datasource import DataSource
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceListResponse,
    DataSourceResponse,
    DataSourceUpdate,
)

router = APIRouter()
logger = structlog.get_logger()


@router.post(
    "/datasources",
    response_model=DataSourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new data source",
)
async def create_datasource(
    payload: DataSourceCreate,
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    """Register a data source (PostgreSQL, BigQuery, etc.) to monitor."""
    # Check name uniqueness
    existing = await db.execute(
        select(DataSource).where(DataSource.name == payload.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A data source named '{payload.name}' already exists.",
        )

    datasource = DataSource(**payload.model_dump())
    db.add(datasource)
    await db.flush()

    logger.info("datasource_created", id=str(datasource.id), name=datasource.name)
    return DataSourceResponse.model_validate(datasource)


@router.get(
    "/datasources",
    response_model=DataSourceListResponse,
    summary="List all data sources",
)
async def list_datasources(
    org_id: str = Query("default"),
    enabled_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> DataSourceListResponse:
    """List all registered data sources for an org."""
    q = select(DataSource).where(DataSource.org_id == org_id)
    if enabled_only:
        q = q.where(DataSource.enabled == True)  # noqa: E712

    count_result = await db.execute(select(func.count()).select_from(q.subquery()))
    total = count_result.scalar_one()

    items_result = await db.execute(q.order_by(DataSource.created_at.desc()).limit(limit).offset(offset))
    items = items_result.scalars().all()

    return DataSourceListResponse(
        items=[DataSourceResponse.model_validate(ds) for ds in items],
        total=total,
    )


@router.get(
    "/datasources/{datasource_id}",
    response_model=DataSourceResponse,
    summary="Get a data source by ID",
)
async def get_datasource(
    datasource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    datasource = result.scalar_one_or_none()
    if not datasource:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return DataSourceResponse.model_validate(datasource)


@router.patch(
    "/datasources/{datasource_id}",
    response_model=DataSourceResponse,
    summary="Update a data source",
)
async def update_datasource(
    datasource_id: uuid.UUID,
    payload: DataSourceUpdate,
    db: AsyncSession = Depends(get_db),
) -> DataSourceResponse:
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    datasource = result.scalar_one_or_none()
    if not datasource:
        raise HTTPException(status_code=404, detail="DataSource not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(datasource, field, value)

    await db.flush()
    await db.refresh(datasource)
    logger.info("datasource_updated", id=str(datasource_id))
    return DataSourceResponse.model_validate(datasource)


@router.delete(
    "/datasources/{datasource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a data source",
)
async def delete_datasource(
    datasource_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    datasource = result.scalar_one_or_none()
    if not datasource:
        raise HTTPException(status_code=404, detail="DataSource not found")

    await db.delete(datasource)
    logger.info("datasource_deleted", id=str(datasource_id))
